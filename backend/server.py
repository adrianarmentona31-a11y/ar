from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal, List

import bcrypt
import httpx
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from pdf_receipt import build_receipt_pdf, ASSETS_DIR  # noqa: F401

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("armenta_os")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_HOURS = 24 * 7


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Armenta's Motors Company API", version="0.3.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password + JWT
# ---------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "exp": now_dt() + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
        "iat": now_dt(),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    # 1) Bearer JWT (existing custom auth)
    token = creds.credentials if creds and creds.scheme.lower() == "bearer" else None
    if token:
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Token inválido")
            user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
            if not user:
                raise HTTPException(status_code=401, detail="Usuario no encontrado")
            user.pop("password_hash", None)
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Sesión expirada")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Token inválido")

    # 2) session_token cookie (Emergent Google auth)
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        sess = await db.user_sessions.find_one({"session_token": cookie_token}, {"_id": 0})
        if not sess:
            raise HTTPException(status_code=401, detail="Sesión inválida")
        expires_at = sess.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < now_dt():
            raise HTTPException(status_code=401, detail="Sesión expirada")
        user = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        user.pop("password_hash", None)
        return user

    raise HTTPException(status_code=401, detail="No autenticado")


def require_role(*roles: str):
    async def _dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return user
    return _dep


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------
Role = Literal["admin", "manager", "technician", "assistant", "viewer"]


def _strip(v):
    return v.strip() if isinstance(v, str) else v


def _clean_doc(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    for k, v in list(doc.items()):
        if isinstance(v, str) and k in ("created_at", "updated_at") and v:
            try:
                doc[k] = datetime.fromisoformat(v)
            except Exception:
                pass
    return doc


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    username: str
    email: EmailStr
    name: str
    role: Role
    created_at: datetime


class LoginBody(BaseModel):
    identifier: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    token: str
    user: UserPublic
    session_started_at: datetime


@api.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginBody):
    identifier = body.identifier.strip().lower()
    if not identifier or not body.password:
        raise HTTPException(status_code=400, detail="Ingresa usuario y contraseña.")
    user_doc = await db.users.find_one(
        {"$or": [{"username": identifier}, {"email": identifier}]}
    )
    if not user_doc or not verify_password(body.password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    token = create_access_token(user_doc["id"], user_doc["username"], user_doc["role"])
    started = now_dt()
    await db.users.update_one({"id": user_doc["id"]}, {"$set": {"last_login_at": started.isoformat()}})
    user_doc = _clean_doc(user_doc)
    user_doc.pop("password_hash", None)
    return LoginResponse(token=token, user=UserPublic(**user_doc), session_started_at=started)


@api.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**_clean_doc(user))


@api.post("/auth/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    cookie_token = request.cookies.get("session_token")
    resp = JSONResponse({"ok": True})
    if cookie_token:
        await db.user_sessions.delete_one({"session_token": cookie_token})
        resp.delete_cookie("session_token", path="/")
    return resp


# --- Emergent-managed Google Sign-In ---
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
@api.post("/auth/session")
async def google_session_exchange(request: Request):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        try:
            body = await request.json()
            session_id = (body or {}).get("session_id")
        except Exception:
            session_id = None
    if not session_id:
        raise HTTPException(status_code=400, detail="Falta session_id")
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )
    except Exception as exc:
        logger.exception("emergent-auth call failed: %s", exc)
        raise HTTPException(status_code=502, detail="No se pudo contactar al proveedor de autenticación")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Sesión de Google inválida")
    data = r.json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google no devolvió correo")
    name = data.get("name") or email
    picture = data.get("picture") or ""
    session_token = data.get("session_token")
    if not session_token:
        raise HTTPException(status_code=502, detail="Respuesta de Google incompleta")
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    user_doc = await db.users.find_one({"email": email})
    if user_doc is None:
        user_doc = {
            "id": str(uuid.uuid4()),
            "username": email, "email": email, "name": name,
            "role": "admin" if email == admin_email else "viewer",
            "picture": picture, "google_linked": True,
            "created_at": now_iso(), "last_login_at": now_iso(),
        }
        await db.users.insert_one(user_doc)
    else:
        await db.users.update_one(
            {"id": user_doc["id"]},
            {"$set": {"name": name, "picture": picture, "google_linked": True, "last_login_at": now_iso()}},
        )
        user_doc.update({"name": name, "picture": picture})
    expires_at = now_dt() + timedelta(days=7)
    await db.user_sessions.insert_one({
        "session_token": session_token, "user_id": user_doc["id"],
        "expires_at": expires_at.isoformat(), "created_at": now_iso(),
    })
    resp = JSONResponse({
        "user": {
            "id": user_doc["id"],
            "username": user_doc.get("username", email),
            "email": email, "name": user_doc.get("name", name),
            "role": user_doc.get("role", "viewer"),
            "picture": user_doc.get("picture", picture),
        },
        "session_started_at": now_iso(),
    })
    resp.set_cookie(
        key="session_token", value=session_token,
        httponly=True, secure=True, samesite="none",
        max_age=7 * 24 * 3600, path="/",
    )
    return resp


# ---------------------------------------------------------------------------
# FILE & MEDIA STORAGE (Emergent object storage)
# ---------------------------------------------------------------------------
import mimetypes as _mimetypes
from fastapi import UploadFile, File as FastFile, Query, Header  # noqa: E402
from storage import init_storage, put_object, get_object  # noqa: E402


class FileOut(BaseModel):
    id: str
    storage_path: str
    original_filename: str
    content_type: str
    size: int
    service_id: Optional[str] = None
    created_at: datetime


@api.post("/files/upload", response_model=FileOut, status_code=201)
async def upload_file(
    file: UploadFile = FastFile(...),
    service_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    max_bytes = 12 * 1024 * 1024  # 12 MB
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande (máx 12 MB)")
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp", "gif", "pdf"}:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")
    content_type = file.content_type or _mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    file_id = str(uuid.uuid4())
    path = f"armenta-os/uploads/{user['id']}/{file_id}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as exc:
        logger.exception("upload failed: %s", exc)
        raise HTTPException(status_code=502, detail="No se pudo guardar el archivo")
    doc = {
        "id": file_id,
        "storage_path": result["path"],
        "original_filename": file.filename or f"{file_id}.{ext}",
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "service_id": service_id,
        "uploaded_by": user["id"],
        "is_deleted": False,
        "created_at": now_iso(),
    }
    await db.files.insert_one(doc)
    if service_id:
        await db.services.update_one(
            {"id": service_id},
            {"$addToSet": {"photos": file_id}, "$set": {"updated_at": now_iso()}},
        )
    return FileOut(**_clean_doc(doc))


@api.get("/files")
async def list_files(user: dict = Depends(get_current_user), service_id: Optional[str] = None):
    filt = {"is_deleted": False}
    if service_id:
        filt["service_id"] = service_id
    docs = await db.files.find(filt).sort("created_at", -1).limit(200).to_list(200)
    return {"items": [FileOut(**_clean_doc(d)).model_dump() for d in docs]}


@api.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth: Optional[str] = Query(None, description="Bearer token via query for <img> src"),
):
    # Support <img src="...?auth=TOKEN"> since <img> can't send headers
    if not (creds and creds.scheme.lower() == "bearer") and auth:
        request._headers = None  # noqa - just guard
    # Re-run auth resolution manually so we can accept the query token too
    token = creds.credentials if creds and creds.scheme.lower() == "bearer" else auth
    if token:
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Token inválido")
            if not await db.users.find_one({"id": payload["sub"]}, {"_id": 1}):
                raise HTTPException(status_code=401, detail="Usuario no encontrado")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Token inválido")
    else:
        cookie_token = request.cookies.get("session_token")
        if not cookie_token:
            raise HTTPException(status_code=401, detail="No autenticado")
        sess = await db.user_sessions.find_one({"session_token": cookie_token})
        if not sess:
            raise HTTPException(status_code=401, detail="Sesión inválida")
    record = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        data, ct = get_object(record["storage_path"])
    except Exception as exc:
        logger.exception("storage get failed: %s", exc)
        raise HTTPException(status_code=502, detail="No se pudo recuperar el archivo")
    return Response(
        content=data,
        media_type=record.get("content_type") or ct,
        headers={"Content-Disposition": f'inline; filename="{record["original_filename"]}"'},
    )


@api.delete("/files/{file_id}")
async def soft_delete_file(file_id: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.files.update_one({"id": file_id}, {"$set": {"is_deleted": True, "updated_at": now_iso()}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    # detach from any service
    await db.services.update_many({"photos": file_id}, {"$pull": {"photos": file_id}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# CLIENTES
# ---------------------------------------------------------------------------
ClientType = Literal["particular", "empresa", "lote"]


class ClientCreate(BaseModel):
    tipo: ClientType = "particular"
    nombre: str = Field(..., min_length=1, max_length=160)
    telefono: Optional[str] = ""
    email: Optional[str] = ""
    direccion: Optional[str] = ""
    notas: Optional[str] = ""
    company_id: Optional[str] = None


class ClientUpdate(BaseModel):
    tipo: Optional[ClientType] = None
    nombre: Optional[str] = Field(default=None, min_length=1)
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None
    company_id: Optional[str] = None


class ClientOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    tipo: ClientType
    nombre: str
    telefono: str = ""
    email: str = ""
    direccion: str = ""
    notas: str = ""
    company_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def _client_out(doc: dict) -> ClientOut:
    return ClientOut(**_clean_doc(doc))


@api.post("/clients", response_model=ClientOut, status_code=201)
async def create_client(body: ClientCreate, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "tipo": body.tipo,
        "nombre": _strip(body.nombre),
        "telefono": _strip(body.telefono or ""),
        "email": (body.email or "").strip().lower(),
        "direccion": _strip(body.direccion or ""),
        "notas": _strip(body.notas or ""),
        "company_id": body.company_id,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.clients.insert_one(doc)
    return _client_out(doc)


@api.get("/clients")
async def list_clients(
    user: dict = Depends(get_current_user),
    q: Optional[str] = None,
    tipo: Optional[ClientType] = None,
    limit: int = 200, skip: int = 0,
):
    limit = max(1, min(500, limit))
    filt: dict = {}
    if tipo: filt["tipo"] = tipo
    if q:
        rgx = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"nombre": rgx}, {"telefono": rgx}, {"email": rgx}, {"direccion": rgx}]
    cursor = db.clients.find(filt).sort("created_at", -1).skip(max(0, skip)).limit(limit)
    docs = await cursor.to_list(limit)
    total = await db.clients.count_documents(filt)
    return {"items": [_client_out(d).model_dump() for d in docs], "total": total, "limit": limit, "skip": skip}


@api.get("/clients/{cid}", response_model=ClientOut)
async def get_client(cid: str, user: dict = Depends(get_current_user)):
    doc = await db.clients.find_one({"id": cid})
    if not doc: raise HTTPException(404, "Cliente no encontrado")
    return _client_out(doc)


@api.patch("/clients/{cid}", response_model=ClientOut)
async def update_client(cid: str, body: ClientUpdate, user: dict = Depends(get_current_user)):
    doc = await db.clients.find_one({"id": cid})
    if not doc: raise HTTPException(404, "Cliente no encontrado")
    patch = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "email" in patch and isinstance(patch["email"], str): patch["email"] = patch["email"].lower()
    patch["updated_at"] = now_iso()
    await db.clients.update_one({"id": cid}, {"$set": patch})
    return _client_out(await db.clients.find_one({"id": cid}))


@api.delete("/clients/{cid}")
async def delete_client(cid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.clients.delete_one({"id": cid})
    if r.deleted_count == 0: raise HTTPException(404, "Cliente no encontrado")
    return {"ok": True, "id": cid}


# ---------------------------------------------------------------------------
# EMPRESAS
# ---------------------------------------------------------------------------
class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1)
    contact: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    rfc: Optional[str] = ""
    payment_terms_days: Optional[int] = 0
    credit_limit: Optional[float] = 0.0
    notes: Optional[str] = ""


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    rfc: Optional[str] = None
    payment_terms_days: Optional[int] = None
    credit_limit: Optional[float] = None
    notes: Optional[str] = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    contact: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    rfc: str = ""
    payment_terms_days: int = 0
    credit_limit: float = 0.0
    notes: str = ""
    created_at: datetime
    updated_at: datetime


@api.post("/companies", response_model=CompanyOut, status_code=201)
async def create_company(body: CompanyCreate, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "id": str(uuid.uuid4()),
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": user["id"],
    })
    for k in ("name", "contact", "phone", "address", "rfc", "notes"):
        if isinstance(doc.get(k), str): doc[k] = doc[k].strip()
    if isinstance(doc.get("email"), str): doc["email"] = doc["email"].strip().lower()
    await db.companies.insert_one(doc)
    return CompanyOut(**_clean_doc(doc))


@api.get("/companies")
async def list_companies(user: dict = Depends(get_current_user), q: Optional[str] = None):
    filt = {}
    if q:
        rgx = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"name": rgx}, {"rfc": rgx}, {"contact": rgx}, {"email": rgx}]
    docs = await db.companies.find(filt).sort("created_at", -1).to_list(500)
    return {"items": [CompanyOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.companies.count_documents(filt)}


@api.patch("/companies/{cid}", response_model=CompanyOut)
async def update_company(cid: str, body: CompanyUpdate, user: dict = Depends(get_current_user)):
    doc = await db.companies.find_one({"id": cid})
    if not doc: raise HTTPException(404, "Empresa no encontrada")
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    patch["updated_at"] = now_iso()
    await db.companies.update_one({"id": cid}, {"$set": patch})
    return CompanyOut(**_clean_doc(await db.companies.find_one({"id": cid})))


@api.delete("/companies/{cid}")
async def delete_company(cid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.companies.delete_one({"id": cid})
    if r.deleted_count == 0: raise HTTPException(404, "Empresa no encontrada")
    return {"ok": True}


# ---------------------------------------------------------------------------
# VEHÍCULOS
# ---------------------------------------------------------------------------
class VehicleCreate(BaseModel):
    client_id: str
    year: Optional[int] = None
    make: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    engine: Optional[str] = ""
    vin: Optional[str] = ""
    plates: Optional[str] = ""
    mileage: Optional[int] = 0
    drive: Optional[str] = ""
    color: Optional[str] = ""
    notes: Optional[str] = ""
    next_service_km: Optional[int] = None
    next_service_date: Optional[str] = None


class VehicleUpdate(BaseModel):
    client_id: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    engine: Optional[str] = None
    vin: Optional[str] = None
    plates: Optional[str] = None
    mileage: Optional[int] = None
    drive: Optional[str] = None
    color: Optional[str] = None
    notes: Optional[str] = None
    next_service_km: Optional[int] = None
    next_service_date: Optional[str] = None


class VehicleOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    year: Optional[int] = None
    make: str
    model: str
    engine: str = ""
    vin: str = ""
    plates: str = ""
    mileage: int = 0
    drive: str = ""
    color: str = ""
    notes: str = ""
    next_service_km: Optional[int] = None
    next_service_date: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@api.post("/vehicles", response_model=VehicleOut, status_code=201)
async def create_vehicle(body: VehicleCreate, user: dict = Depends(get_current_user)):
    if not await db.clients.find_one({"id": body.client_id}):
        raise HTTPException(400, "Cliente no válido")
    doc = body.model_dump()
    for k in ("make", "model", "engine", "vin", "plates", "drive", "color", "notes"):
        if isinstance(doc.get(k), str): doc[k] = doc[k].strip()
    if isinstance(doc.get("vin"), str): doc["vin"] = doc["vin"].upper()
    if isinstance(doc.get("plates"), str): doc["plates"] = doc["plates"].upper()
    doc.update({
        "id": str(uuid.uuid4()),
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": user["id"],
    })
    await db.vehicles.insert_one(doc)
    return VehicleOut(**_clean_doc(doc))


@api.get("/vehicles")
async def list_vehicles(
    user: dict = Depends(get_current_user),
    q: Optional[str] = None, client_id: Optional[str] = None,
    limit: int = 200,
):
    filt = {}
    if client_id: filt["client_id"] = client_id
    if q:
        rgx = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"make": rgx}, {"model": rgx}, {"vin": rgx}, {"plates": rgx}]
    docs = await db.vehicles.find(filt).sort("created_at", -1).limit(limit).to_list(limit)
    total = await db.vehicles.count_documents(filt)
    # enrich with client
    client_ids = list({d["client_id"] for d in docs if d.get("client_id")})
    clients = {c["id"]: c["nombre"] for c in await db.clients.find({"id": {"$in": client_ids}}).to_list(len(client_ids) or 1)}
    items = []
    for d in docs:
        out = VehicleOut(**_clean_doc(d)).model_dump()
        out["client_name"] = clients.get(d.get("client_id"), "")
        items.append(out)
    return {"items": items, "total": total}


@api.get("/vehicles/{vid}", response_model=VehicleOut)
async def get_vehicle(vid: str, user: dict = Depends(get_current_user)):
    doc = await db.vehicles.find_one({"id": vid})
    if not doc: raise HTTPException(404, "Vehículo no encontrado")
    return VehicleOut(**_clean_doc(doc))


@api.patch("/vehicles/{vid}", response_model=VehicleOut)
async def update_vehicle(vid: str, body: VehicleUpdate, user: dict = Depends(get_current_user)):
    doc = await db.vehicles.find_one({"id": vid})
    if not doc: raise HTTPException(404, "Vehículo no encontrado")
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    for k in ("make", "model", "engine", "vin", "plates", "drive", "color", "notes"):
        if k in patch and isinstance(patch[k], str): patch[k] = patch[k].strip()
    if isinstance(patch.get("vin"), str): patch["vin"] = patch["vin"].upper()
    if isinstance(patch.get("plates"), str): patch["plates"] = patch["plates"].upper()
    patch["updated_at"] = now_iso()
    await db.vehicles.update_one({"id": vid}, {"$set": patch})
    return VehicleOut(**_clean_doc(await db.vehicles.find_one({"id": vid})))


@api.delete("/vehicles/{vid}")
async def delete_vehicle(vid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.vehicles.delete_one({"id": vid})
    if r.deleted_count == 0: raise HTTPException(404, "Vehículo no encontrado")
    return {"ok": True}


# ---------------------------------------------------------------------------
# TÉCNICOS
# ---------------------------------------------------------------------------
class TechnicianCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: Optional[str] = ""
    role: Optional[str] = "technician"
    commission_type: Optional[str] = "percentage"  # percentage | fixed | none
    commission_value: Optional[float] = 0.0
    active: bool = True


class TechnicianUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    commission_type: Optional[str] = None
    commission_value: Optional[float] = None
    active: Optional[bool] = None


class TechnicianOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    phone: str = ""
    role: str = "technician"
    commission_type: str = "percentage"
    commission_value: float = 0.0
    active: bool = True
    created_at: datetime
    updated_at: datetime


@api.post("/technicians", response_model=TechnicianOut, status_code=201)
async def create_tech(body: TechnicianCreate, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({"id": str(uuid.uuid4()), "created_at": now_iso(), "updated_at": now_iso()})
    await db.technicians.insert_one(doc)
    return TechnicianOut(**_clean_doc(doc))


@api.get("/technicians")
async def list_techs(user: dict = Depends(get_current_user)):
    docs = await db.technicians.find().sort("created_at", -1).to_list(500)
    return {"items": [TechnicianOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.technicians.count_documents({})}


@api.patch("/technicians/{tid}", response_model=TechnicianOut)
async def update_tech(tid: str, body: TechnicianUpdate, user: dict = Depends(get_current_user)):
    doc = await db.technicians.find_one({"id": tid})
    if not doc: raise HTTPException(404, "Técnico no encontrado")
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    patch["updated_at"] = now_iso()
    await db.technicians.update_one({"id": tid}, {"$set": patch})
    return TechnicianOut(**_clean_doc(await db.technicians.find_one({"id": tid})))


@api.delete("/technicians/{tid}")
async def delete_tech(tid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.technicians.delete_one({"id": tid})
    if r.deleted_count == 0: raise HTTPException(404, "Técnico no encontrado")
    return {"ok": True}


# ---------------------------------------------------------------------------
# QUOTES / RECIBOS
# ---------------------------------------------------------------------------
QuoteStatus = Literal["draft", "sent", "approved", "rejected", "expired"]


class QuoteItem(BaseModel):
    description: str = Field(..., min_length=1)
    quantity: float = 1.0
    unit_price: float = 0.0
    cost: float = 0.0  # for profit
    is_labor: bool = False


class QuoteCreate(BaseModel):
    client_id: str
    vehicle_id: Optional[str] = None
    items: List[QuoteItem] = []
    tax_rate: float = 0.16  # IVA 16%
    notes: Optional[str] = ""
    valid_days: int = 15


class QuoteUpdate(BaseModel):
    client_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    items: Optional[List[QuoteItem]] = None
    tax_rate: Optional[float] = None
    notes: Optional[str] = None
    valid_days: Optional[int] = None
    status: Optional[QuoteStatus] = None


class QuoteOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    folio: str
    client_id: str
    vehicle_id: Optional[str] = None
    items: List[QuoteItem] = []
    subtotal: float
    tax_rate: float
    tax: float
    total: float
    cost_total: float
    profit: float
    status: QuoteStatus
    notes: str = ""
    valid_days: int = 15
    expires_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def _totals(items: List[QuoteItem], tax_rate: float):
    subtotal = sum((it.quantity or 0) * (it.unit_price or 0) for it in items)
    cost = sum((it.quantity or 0) * (it.cost or 0) for it in items)
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    return round(subtotal, 2), tax, total, round(cost, 2), round(subtotal - cost, 2)


async def _next_folio(prefix: str, coll) -> str:
    year = now_dt().year
    key = f"{prefix}-{year}"
    seq = await db.counters.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq_num = seq.get("seq", 1) if seq else 1
    return f"{prefix}-{year}-{seq_num:04d}"


@api.post("/quotes", response_model=QuoteOut, status_code=201)
async def create_quote(body: QuoteCreate, user: dict = Depends(get_current_user)):
    if not await db.clients.find_one({"id": body.client_id}):
        raise HTTPException(400, "Cliente no válido")
    items = body.items or []
    subtotal, tax, total, cost, profit = _totals(items, body.tax_rate)
    folio = await _next_folio("COT", db.quotes)
    doc = {
        "id": str(uuid.uuid4()),
        "folio": folio,
        "client_id": body.client_id,
        "vehicle_id": body.vehicle_id,
        "items": [it.model_dump() for it in items],
        "subtotal": subtotal, "tax_rate": body.tax_rate, "tax": tax, "total": total,
        "cost_total": cost, "profit": profit,
        "status": "draft",
        "notes": (body.notes or "").strip(),
        "valid_days": body.valid_days,
        "expires_at": (now_dt() + timedelta(days=body.valid_days)).isoformat(),
        "created_by": user["id"],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.quotes.insert_one(doc)
    return QuoteOut(**_clean_doc(doc))


@api.get("/quotes")
async def list_quotes(user: dict = Depends(get_current_user), status: Optional[QuoteStatus] = None, client_id: Optional[str] = None):
    filt = {}
    if status: filt["status"] = status
    if client_id: filt["client_id"] = client_id
    docs = await db.quotes.find(filt).sort("created_at", -1).limit(300).to_list(300)
    return {"items": [QuoteOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.quotes.count_documents(filt)}


@api.get("/quotes/{qid}")
async def get_quote(qid: str, user: dict = Depends(get_current_user)):
    doc = await db.quotes.find_one({"id": qid})
    if not doc: raise HTTPException(404, "Cotización no encontrada")
    q = QuoteOut(**_clean_doc(doc)).model_dump()
    # enrich for receipt view
    if doc.get("client_id"):
        c = await db.clients.find_one({"id": doc["client_id"]})
        if c:
            c = _clean_doc(c)
            c.pop("password_hash", None)
            q["client"] = {k: c.get(k) for k in ("id","tipo","nombre","telefono","email","direccion")}
    if doc.get("vehicle_id"):
        v = await db.vehicles.find_one({"id": doc["vehicle_id"]})
        if v:
            v = _clean_doc(v)
            q["vehicle"] = {k: v.get(k) for k in ("id","year","make","model","engine","vin","plates","mileage","color")}
    return q


@api.patch("/quotes/{qid}", response_model=QuoteOut)
async def update_quote(qid: str, body: QuoteUpdate, user: dict = Depends(get_current_user)):
    doc = await db.quotes.find_one({"id": qid})
    if not doc: raise HTTPException(404, "Cotización no encontrada")
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    # recompute if items or tax change
    items_src = patch.get("items", doc["items"])
    tax_rate = patch.get("tax_rate", doc["tax_rate"])
    items = [QuoteItem(**it) if isinstance(it, dict) else it for it in items_src]
    if "items" in patch or "tax_rate" in patch:
        subtotal, tax, total, cost, profit = _totals(items, tax_rate)
        patch.update({"items": [it.model_dump() for it in items], "subtotal": subtotal, "tax_rate": tax_rate, "tax": tax, "total": total, "cost_total": cost, "profit": profit})
    patch["updated_at"] = now_iso()
    await db.quotes.update_one({"id": qid}, {"$set": patch})
    return QuoteOut(**_clean_doc(await db.quotes.find_one({"id": qid})))


@api.delete("/quotes/{qid}")
async def delete_quote(qid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.quotes.delete_one({"id": qid})
    if r.deleted_count == 0: raise HTTPException(404, "Cotización no encontrada")
    return {"ok": True}


# ---------------------------------------------------------------------------
# SERVICIOS (WORK ORDERS)
# ---------------------------------------------------------------------------
ServiceStatus = Literal[
    "lead", "diagnostic", "quoted", "approved", "scheduled",
    "in_progress", "completed", "delivered", "cancelled",
]


class ServiceCreate(BaseModel):
    client_id: str
    vehicle_id: Optional[str] = None
    technician_id: Optional[str] = None
    type: Optional[str] = "mantenimiento"  # diagnóstico, mantenimiento, afinación, reparación, inspección
    symptoms: Optional[str] = ""
    diagnosis: Optional[str] = ""
    requested_service: Optional[str] = ""
    scheduled_at: Optional[str] = None  # ISO date
    address: Optional[str] = ""
    items: List[QuoteItem] = []
    tax_rate: float = 0.16
    notes: Optional[str] = ""


class ServiceUpdate(BaseModel):
    client_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    technician_id: Optional[str] = None
    type: Optional[str] = None
    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    requested_service: Optional[str] = None
    status: Optional[ServiceStatus] = None
    scheduled_at: Optional[str] = None
    address: Optional[str] = None
    items: Optional[List[QuoteItem]] = None
    tax_rate: Optional[float] = None
    notes: Optional[str] = None
    recommendations: Optional[str] = None
    next_service_km: Optional[int] = None
    next_service_date: Optional[str] = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    folio: str
    client_id: str
    vehicle_id: Optional[str] = None
    technician_id: Optional[str] = None
    type: str = "mantenimiento"
    symptoms: str = ""
    diagnosis: str = ""
    requested_service: str = ""
    status: ServiceStatus = "lead"
    scheduled_at: Optional[str] = None
    address: str = ""
    items: List[QuoteItem] = []
    subtotal: float = 0.0
    tax_rate: float = 0.16
    tax: float = 0.0
    total: float = 0.0
    cost_total: float = 0.0
    profit: float = 0.0
    paid: float = 0.0
    balance: float = 0.0
    notes: str = ""
    recommendations: str = ""
    next_service_km: Optional[int] = None
    next_service_date: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@api.post("/services", response_model=ServiceOut, status_code=201)
async def create_service(body: ServiceCreate, user: dict = Depends(get_current_user)):
    if not await db.clients.find_one({"id": body.client_id}):
        raise HTTPException(400, "Cliente no válido")
    items = body.items or []
    subtotal, tax, total, cost, profit = _totals(items, body.tax_rate)
    folio = await _next_folio("OS", db.services)
    doc = {
        "id": str(uuid.uuid4()),
        "folio": folio,
        "client_id": body.client_id,
        "vehicle_id": body.vehicle_id,
        "technician_id": body.technician_id,
        "type": (body.type or "mantenimiento").strip(),
        "symptoms": (body.symptoms or "").strip(),
        "diagnosis": (body.diagnosis or "").strip(),
        "requested_service": (body.requested_service or "").strip(),
        "status": "lead",
        "scheduled_at": body.scheduled_at,
        "address": (body.address or "").strip(),
        "items": [it.model_dump() for it in items],
        "subtotal": subtotal, "tax_rate": body.tax_rate, "tax": tax, "total": total,
        "cost_total": cost, "profit": profit,
        "paid": 0.0, "balance": total,
        "notes": (body.notes or "").strip(),
        "recommendations": "",
        "next_service_km": None, "next_service_date": None,
        "created_by": user["id"],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.services.insert_one(doc)
    return ServiceOut(**_clean_doc(doc))


async def _recalc_service_balance(sid: str):
    doc = await db.services.find_one({"id": sid})
    if not doc: return
    total = doc.get("total", 0.0)
    paid = 0.0
    async for p in db.payments.find({"service_id": sid}):
        paid += p.get("amount", 0.0)
    await db.services.update_one({"id": sid}, {"$set": {"paid": round(paid, 2), "balance": round(total - paid, 2), "updated_at": now_iso()}})


@api.get("/services")
async def list_services(
    user: dict = Depends(get_current_user),
    status: Optional[ServiceStatus] = None,
    client_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
):
    filt = {}
    if status: filt["status"] = status
    if client_id: filt["client_id"] = client_id
    if vehicle_id: filt["vehicle_id"] = vehicle_id
    docs = await db.services.find(filt).sort("created_at", -1).limit(300).to_list(300)
    return {"items": [ServiceOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.services.count_documents(filt)}


@api.get("/services/{sid}")
async def get_service(sid: str, user: dict = Depends(get_current_user)):
    doc = await db.services.find_one({"id": sid})
    if not doc: raise HTTPException(404, "Servicio no encontrado")
    s = ServiceOut(**_clean_doc(doc)).model_dump()
    if doc.get("client_id"):
        c = await db.clients.find_one({"id": doc["client_id"]})
        if c: s["client"] = {k: _clean_doc(c).get(k) for k in ("id","tipo","nombre","telefono","email","direccion")}
    if doc.get("vehicle_id"):
        v = await db.vehicles.find_one({"id": doc["vehicle_id"]})
        if v: s["vehicle"] = {k: _clean_doc(v).get(k) for k in ("id","year","make","model","engine","vin","plates","mileage","color")}
    if doc.get("technician_id"):
        t = await db.technicians.find_one({"id": doc["technician_id"]})
        if t: s["technician"] = {"id": t["id"], "name": t.get("name","")}
    return s


@api.patch("/services/{sid}", response_model=ServiceOut)
async def update_service(sid: str, body: ServiceUpdate, user: dict = Depends(get_current_user)):
    doc = await db.services.find_one({"id": sid})
    if not doc: raise HTTPException(404, "Servicio no encontrado")
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    items_src = patch.get("items", doc["items"])
    tax_rate = patch.get("tax_rate", doc["tax_rate"])
    if "items" in patch or "tax_rate" in patch:
        items = [QuoteItem(**it) if isinstance(it, dict) else it for it in items_src]
        subtotal, tax, total, cost, profit = _totals(items, tax_rate)
        patch.update({"items": [it.model_dump() for it in items], "subtotal": subtotal, "tax_rate": tax_rate, "tax": tax, "total": total, "cost_total": cost, "profit": profit, "balance": round(total - doc.get("paid", 0.0), 2)})
    patch["updated_at"] = now_iso()
    await db.services.update_one({"id": sid}, {"$set": patch})
    return ServiceOut(**_clean_doc(await db.services.find_one({"id": sid})))


@api.delete("/services/{sid}")
async def delete_service(sid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.services.delete_one({"id": sid})
    if r.deleted_count == 0: raise HTTPException(404, "Servicio no encontrado")
    await db.payments.delete_many({"service_id": sid})
    return {"ok": True}


# ---------------------------------------------------------------------------
# PAGOS / COBROS
# ---------------------------------------------------------------------------
PaymentMethod = Literal["cash", "transfer", "card", "other"]


class PaymentCreate(BaseModel):
    service_id: Optional[str] = None
    quote_id: Optional[str] = None
    client_id: Optional[str] = None
    amount: float = Field(..., gt=0)
    method: PaymentMethod = "cash"
    reference: Optional[str] = ""
    notes: Optional[str] = ""
    date: Optional[str] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    folio: str
    service_id: Optional[str] = None
    quote_id: Optional[str] = None
    client_id: Optional[str] = None
    amount: float
    method: PaymentMethod
    reference: str = ""
    notes: str = ""
    date: str
    created_at: datetime


@api.post("/payments", response_model=PaymentOut, status_code=201)
async def create_payment(body: PaymentCreate, user: dict = Depends(get_current_user)):
    folio = await _next_folio("PAG", db.payments)
    date = body.date or now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "folio": folio,
        "service_id": body.service_id, "quote_id": body.quote_id, "client_id": body.client_id,
        "amount": round(body.amount, 2),
        "method": body.method,
        "reference": (body.reference or "").strip(),
        "notes": (body.notes or "").strip(),
        "date": date,
        "created_by": user["id"],
        "created_at": now_iso(),
    }
    await db.payments.insert_one(doc)
    if body.service_id:
        await _recalc_service_balance(body.service_id)
    return PaymentOut(**_clean_doc(doc))


@api.get("/payments")
async def list_payments(user: dict = Depends(get_current_user), service_id: Optional[str] = None, client_id: Optional[str] = None):
    filt = {}
    if service_id: filt["service_id"] = service_id
    if client_id: filt["client_id"] = client_id
    docs = await db.payments.find(filt).sort("created_at", -1).limit(300).to_list(300)
    return {"items": [PaymentOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.payments.count_documents(filt)}


@api.delete("/payments/{pid}")
async def delete_payment(pid: str, user: dict = Depends(require_role("admin", "manager"))):
    doc = await db.payments.find_one({"id": pid})
    if not doc: raise HTTPException(404, "Pago no encontrado")
    await db.payments.delete_one({"id": pid})
    if doc.get("service_id"): await _recalc_service_balance(doc["service_id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# CONFIGURACIÓN (single settings doc)
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_rfc: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    company_address: Optional[str] = None
    tax_rate: Optional[float] = None
    currency: Optional[str] = None
    footer_note: Optional[str] = None


DEFAULT_SETTINGS = {
    "company_name": "Armenta's Motors Company",
    "company_rfc": "",
    "company_phone": "",
    "company_email": "adrianarmentona31@gmail.com",
    "company_address": "Ciudad Juárez, Chihuahua",
    "tax_rate": 0.16,
    "currency": "MXN",
    "footer_note": "Gracias por confiar en Armenta's Motors Company. Servicio automotriz móvil profesional.",
}


@api.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    doc = await db.settings.find_one({"_id": "singleton"})
    if not doc:
        doc = {**DEFAULT_SETTINGS, "_id": "singleton"}
        await db.settings.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/settings")
async def update_settings(body: SettingsUpdate, user: dict = Depends(require_role("admin", "manager"))):
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    await db.settings.update_one({"_id": "singleton"}, {"$set": patch}, upsert=True)
    doc = await db.settings.find_one({"_id": "singleton"})
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# DASHBOARD + FINANZAS
# ---------------------------------------------------------------------------
@api.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    today = now_dt().date().isoformat()
    collections = await db.list_collection_names()

    services_today = 0
    if "services" in collections:
        services_today = await db.services.count_documents({"scheduled_at": {"$regex": f"^{today}"}})
    quotes_pending = await db.quotes.count_documents({"status": {"$in": ["draft", "sent"]}}) if "quotes" in collections else 0

    receivable_total = 0.0
    if "services" in collections:
        async for s in db.services.find({"balance": {"$gt": 0}}, {"balance": 1}):
            receivable_total += s.get("balance", 0.0)

    clients_total = await db.clients.count_documents({}) if "clients" in collections else 0
    vehicles_total = await db.vehicles.count_documents({}) if "vehicles" in collections else 0

    return {
        "services_today": services_today,
        "quotes_pending": quotes_pending,
        "receivable_total_mxn": round(receivable_total, 2),
        "clients_total": clients_total,
        "vehicles_total": vehicles_total,
        "system_status": "operativo",
        "generated_at": now_iso(),
    }


@api.get("/finance/summary")
async def finance_summary(user: dict = Depends(get_current_user)):
    revenue = 0.0
    cost = 0.0
    profit = 0.0
    async for s in db.services.find({"status": {"$in": ["completed", "delivered"]}}):
        revenue += s.get("total", 0.0)
        cost += s.get("cost_total", 0.0)
        profit += s.get("profit", 0.0)
    collected = 0.0
    async for p in db.payments.find():
        collected += p.get("amount", 0.0)
    receivable = 0.0
    async for s in db.services.find({"balance": {"$gt": 0}}, {"balance": 1}):
        receivable += s.get("balance", 0.0)
    services_by_status = {}
    async for s in db.services.find({}, {"status": 1}):
        st = s.get("status", "lead")
        services_by_status[st] = services_by_status.get(st, 0) + 1
    return {
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "profit": round(profit, 2),
        "margin_pct": round((profit / revenue * 100) if revenue > 0 else 0.0, 2),
        "collected": round(collected, 2),
        "receivable": round(receivable, 2),
        "services_by_status": services_by_status,
    }


@api.get("/health")
async def health():
    return {"status": "ok", "service": "armentas-motors-company", "phase": "2+"}


# ---------------------------------------------------------------------------
# RECIBOS EN PDF
# ---------------------------------------------------------------------------
async def _load_settings_dict() -> dict:
    doc = await db.settings.find_one({"_id": "singleton"})
    if not doc:
        doc = dict(DEFAULT_SETTINGS)
    doc.pop("_id", None)
    return doc


async def _enrich_doc(kind: str, doc: dict) -> dict:
    out = _clean_doc(doc)
    # Convert datetimes back for the PDF renderer (accepts str/datetime)
    if isinstance(out.get("created_at"), datetime):
        out["created_at"] = out["created_at"].isoformat()
    if doc.get("client_id"):
        c = await db.clients.find_one({"id": doc["client_id"]})
        if c: out["client"] = {k: _clean_doc(c).get(k) for k in ("id", "tipo", "nombre", "telefono", "email", "direccion")}
    if doc.get("vehicle_id"):
        v = await db.vehicles.find_one({"id": doc["vehicle_id"]})
        if v: out["vehicle"] = {k: _clean_doc(v).get(k) for k in ("id", "year", "make", "model", "engine", "vin", "plates", "mileage", "color")}
    if kind == "servicio" and doc.get("technician_id"):
        t = await db.technicians.find_one({"id": doc["technician_id"]})
        if t: out["technician"] = {"id": t["id"], "name": t.get("name", "")}
    return out


@api.get("/receipts/{kind}/{doc_id}/pdf")
async def receipt_pdf(kind: str, doc_id: str, user: dict = Depends(get_current_user)):
    if kind not in ("servicio", "cotizacion"):
        raise HTTPException(status_code=400, detail="Tipo inválido")
    coll = db.services if kind == "servicio" else db.quotes
    doc = await coll.find_one({"id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    enriched = await _enrich_doc(kind, doc)
    settings = await _load_settings_dict()
    pdf_bytes = build_receipt_pdf(enriched, settings, kind=kind)
    filename = f"{enriched.get('folio', 'recibo')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Filename": filename,
        },
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
async def ensure_indexes():
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    for coll in ("clients", "companies", "vehicles", "technicians", "quotes", "services", "payments"):
        await db[coll].create_index("id", unique=True)
    await db.clients.create_index("nombre")
    await db.vehicles.create_index("client_id")
    await db.services.create_index("status")
    await db.services.create_index("client_id")
    await db.quotes.create_index("status")
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("expires_at")


async def seed_admin():
    admin_email = os.environ["ADMIN_EMAIL"].strip().lower()
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip().lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    admin_name = os.environ.get("ADMIN_NAME", "Administrador")
    existing = await db.users.find_one({"username": admin_username}) or await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "username": admin_username, "email": admin_email, "name": admin_name, "role": "admin",
            "password_hash": hash_password(admin_password),
            "created_at": now_iso(), "last_login_at": None,
        })
        logger.info("Seeded admin %s", admin_username)
    else:
        if not verify_password(admin_password, existing.get("password_hash", "")):
            await db.users.update_one({"id": existing["id"]}, {"$set": {"password_hash": hash_password(admin_password)}})


@app.on_event("startup")
async def _startup():
    await ensure_indexes()
    await seed_admin()
    try:
        from storage import init_storage as _init
        _init()
    except Exception as exc:
        logger.warning("Storage init failed (uploads will error until fixed): %s", exc)


@app.on_event("shutdown")
async def _shutdown():
    client.close()


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
