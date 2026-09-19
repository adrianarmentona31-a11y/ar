from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import io
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

from pdf_receipt import build_receipt_pdf, build_payment_receipt_pdf, ASSETS_DIR  # noqa: F401

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
            if not user.get("active", True):
                raise HTTPException(status_code=401, detail="Cuenta desactivada")
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
        if not user.get("active", True):
            raise HTTPException(status_code=401, detail="Cuenta desactivada")
        user.pop("password_hash", None)
        return user

    raise HTTPException(status_code=401, detail="No autenticado")


def require_role(*roles: str):
    async def _dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return user
    return _dep


STAFF_ROLES = ("admin", "manager", "technician", "assistant")
require_staff = require_role(*STAFF_ROLES)
require_finance = require_role("admin", "manager")

# --- simple in-memory rate limiting (per process) ---
import time as _time  # noqa: E402
from collections import defaultdict, deque  # noqa: E402
_RATE: dict = defaultdict(deque)


def rate_limit(key: str, limit: int, window_s: int, record: bool = True):
    now = _time.monotonic()
    q = _RATE[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intenta más tarde.")
    if record:
        q.append(now)


def rate_record(key: str):
    _RATE[key].append(_time.monotonic())


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
async def login(body: LoginBody, request: Request):
    identifier = body.identifier.strip().lower()
    if not identifier or not body.password:
        raise HTTPException(status_code=400, detail="Ingresa usuario y contraseña.")
    client_ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    rate_limit(f"login:{client_ip}", 15, 300, record=False)
    rate_limit(f"login:{identifier}", 10, 300, record=False)
    user_doc = await db.users.find_one(
        {"$or": [{"username": identifier}, {"email": identifier}]}
    )
    if not user_doc or not verify_password(body.password, user_doc.get("password_hash", "")):
        rate_record(f"login:{client_ip}"); rate_record(f"login:{identifier}")
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    if not user_doc.get("active", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada.")
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
        if email != admin_email:
            logger.warning("Google sign-in denied for non-invited account: %s", email)
            raise HTTPException(status_code=403, detail="Esta cuenta no está autorizada. Pide al administrador que te invite.")
        user_doc = {
            "id": str(uuid.uuid4()),
            "username": email, "email": email, "name": name,
            "role": "admin",
            "picture": picture, "google_linked": True,
            "created_at": now_iso(), "last_login_at": now_iso(),
        }
        await db.users.insert_one(user_doc)
    if not user_doc.get("active", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada.")
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


@api.get("/files/{file_id}/view-token")
async def file_view_token(file_id: str, user: dict = Depends(get_current_user)):
    if not await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    exp = now_dt() + timedelta(minutes=15)
    tok = jwt.encode({"sub": user["id"], "type": "file", "file_id": file_id, "exp": exp}, get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return {"token": tok, "expires_at": exp.isoformat()}


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
            if auth and not (creds and creds.scheme.lower() == "bearer"):
                if payload.get("type") != "file" or payload.get("file_id") != file_id:
                    raise HTTPException(status_code=401, detail="Token de archivo inválido")
            elif payload.get("type") != "access":
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
    nombre: str = Field(default="", max_length=160)
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
async def create_client(body: ClientCreate, user: dict = Depends(require_staff)):
    doc = {
        "id": str(uuid.uuid4()),
        "tipo": body.tipo,
        "nombre": _strip(body.nombre) or "Cliente sin nombre",
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
async def update_client(cid: str, body: ClientUpdate, user: dict = Depends(require_staff)):
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
async def create_company(body: CompanyCreate, user: dict = Depends(require_staff)):
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
async def update_company(cid: str, body: CompanyUpdate, user: dict = Depends(require_staff)):
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
    client_id: Optional[str] = None
    year: Optional[int] = None
    make: str = ""
    model: str = ""
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
    client_id: Optional[str] = None
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
async def create_vehicle(body: VehicleCreate, user: dict = Depends(require_staff)):
    if body.client_id and not await db.clients.find_one({"id": body.client_id}):
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
async def update_vehicle(vid: str, body: VehicleUpdate, user: dict = Depends(require_staff)):
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
async def create_tech(body: TechnicianCreate, user: dict = Depends(require_staff)):
    doc = body.model_dump()
    doc.update({"id": str(uuid.uuid4()), "created_at": now_iso(), "updated_at": now_iso()})
    await db.technicians.insert_one(doc)
    return TechnicianOut(**_clean_doc(doc))


@api.get("/technicians")
async def list_techs(user: dict = Depends(get_current_user)):
    docs = await db.technicians.find().sort("created_at", -1).to_list(500)
    return {"items": [TechnicianOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.technicians.count_documents({})}


@api.patch("/technicians/{tid}", response_model=TechnicianOut)
async def update_tech(tid: str, body: TechnicianUpdate, user: dict = Depends(require_staff)):
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
    client_id: Optional[str] = None
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
    client_id: Optional[str] = None
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
async def create_quote(body: QuoteCreate, user: dict = Depends(require_staff)):
    if body.client_id and not await db.clients.find_one({"id": body.client_id}):
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
async def update_quote(qid: str, body: QuoteUpdate, user: dict = Depends(require_staff)):
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
    client_id: Optional[str] = None
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
    client_id: Optional[str] = None
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
    receipt_emailed_at: Optional[str] = None
    receipt_emailed_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@api.post("/services", response_model=ServiceOut, status_code=201)
async def create_service(body: ServiceCreate, user: dict = Depends(require_staff)):
    if body.client_id and not await db.clients.find_one({"id": body.client_id}):
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
async def update_service(sid: str, body: ServiceUpdate, user: dict = Depends(require_staff)):
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
async def create_payment(body: PaymentCreate, user: dict = Depends(require_staff)):
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
    survey_url: Optional[str] = None
    bank_holder: Optional[str] = None
    bank_name: Optional[str] = None
    bank_card: Optional[str] = None
    bank_clabe: Optional[str] = None


GOOGLE_FORM_SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeFhlQ9BJmVqCUsWUDu0V1V4VqfiierYdeG-xA4_51csMMgkQ/viewform"

DEFAULT_SETTINGS = {
    "company_name": "Armenta's Motors Company",
    "company_rfc": "",
    "company_phone": "",
    "company_email": "adrianarmentona31@gmail.com",
    "company_address": "Ciudad Juárez, Chihuahua",
    "tax_rate": 0.16,
    "currency": "MXN",
    "footer_note": "Gracias por confiar en Armenta's Motors Company. Servicio automotriz móvil profesional.",
    "survey_url": GOOGLE_FORM_SURVEY_URL,
    "bank_holder": "Adrian Armenta",
    "bank_name": "",
    "bank_card": "",
    "bank_clabe": "",
}


@api.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    doc = await db.settings.find_one({"_id": "singleton"})
    if not doc:
        doc = {**DEFAULT_SETTINGS, "_id": "singleton"}
        await db.settings.insert_one(doc)
    doc.pop("_id", None)
    out = {**DEFAULT_SETTINGS, **doc}
    if user.get("role") not in ("admin", "manager"):
        for k in ("bank_card", "bank_clabe"):
            out.pop(k, None)
    return out


@api.get("/qr")
async def qr_png(data: str = Query(..., min_length=1, max_length=2000)):
    import qrcode
    buf = io.BytesIO()
    qrcode.make(data, box_size=8, border=1).save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


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
async def finance_summary(user: dict = Depends(require_finance)):
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
# CATÁLOGO OFICIAL DE AFINACIÓN (ARMENTA'S MOTORS brand board)
# Sistema de Afinación Multi-Cilindro · precios en MXN
# ---------------------------------------------------------------------------
TUNEUP_CATALOG = {
    "currency": "MXN",
    "tagline": "SERVICIO A DOMICILIO",
    "tiers": [
        {
            "key": "estandar",
            "label": "Calidad Estándar",
            "color": "#d4a94a",
            "spark_plug": {"material": "Cobre", "oil": "Mineral"},
            "prices": {"4": 2500, "6": 3200, "8": 3700},
            "includes": [
                "Cambio de aceite",
                "Verificación de niveles",
                "Filtro de gasolina",
                "Limpieza de gasolina",
                "Limpieza de cuerpo de aceleración",
            ],
        },
        {
            "key": "premium",
            "label": "Calidad Premium",
            "color": "#2f9c4a",
            "spark_plug": {"material": "Platino", "oil": "Semi-sintético"},
            "prices": {"4": 3300, "6": 4000, "8": 4400},
            "includes": [
                "Todo lo Estándar",
                "Limpieza de bornas",
                "Escaneo por computadora",
                "Limpieza válvulas IAC y PVC",
                "Limpieza de inyectores",
            ],
        },
        {
            "key": "lujo",
            "label": "Calidad de Lujo",
            "color": "#1e6feb",
            "spark_plug": {"material": "Iridium", "oil": "Sintético"},
            "prices": {"4": 3900, "6": 4700, "8": 5400},
            "includes": [
                "Todo lo Premium",
                "Verificación de sistema de aceleración",
                "Revisión cuerpo, motor / transmisión",
                "Verificación de suspensión y frenos",
                "Limpieza total con aditivos premium",
            ],
        },
    ],
    "cylinders": [4, 6, 8],
    "spark_plug_options": [
        {"key": "cobre", "label": "Cobre", "family": "Mineral"},
        {"key": "platino", "label": "Platino", "family": "Semi-sintético"},
        {"key": "iridium", "label": "Iridium", "family": "Sintético"},
    ],
}


@api.get("/catalog/tuneups")
async def catalog_tuneups(user: dict = Depends(get_current_user)):
    return TUNEUP_CATALOG


class TuneupPresetItems(BaseModel):
    tier: Literal["estandar", "premium", "lujo"]
    cylinders: Literal[4, 6, 8]


@api.post("/catalog/tuneups/preset-items")
async def tuneup_preset_items(body: TuneupPresetItems, user: dict = Depends(require_staff)):
    """Return QuoteItem[] ready to be dropped into a Service or Quote form."""
    tier = next((t for t in TUNEUP_CATALOG["tiers"] if t["key"] == body.tier), None)
    if not tier:
        raise HTTPException(400, "Nivel no válido")
    price = tier["prices"].get(str(body.cylinders))
    if price is None:
        raise HTTPException(400, "Cilindrada no válida")
    label = f"Afinación {tier['label']} · {body.cylinders} cilindros · bujías {tier['spark_plug']['material']}"
    return {
        "tier": tier["key"],
        "tier_label": tier["label"],
        "cylinders": body.cylinders,
        "items": [
            {
                "description": label + " · " + ", ".join(tier["includes"][:3]),
                "quantity": 1,
                "unit_price": price,
                "cost": round(price * 0.55, 2),  # margen sugerido ~45% (referencia interna)
                "is_labor": False,
            }
        ],
    }


# ---------------------------------------------------------------------------
# AI IMAGE GENERATION (Gemini Nano Banana via Emergent LLM key)
# ---------------------------------------------------------------------------
import base64 as _base64  # noqa: E402
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402


class ImageGenRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=800)
    model: str = "gemini-3.1-flash-image-preview"
    service_id: Optional[str] = None


@api.post("/ai/images/generate")
async def ai_generate_image(body: ImageGenRequest, user: dict = Depends(require_staff)):
    rate_limit(f"ai:{user['id']}", 30, 24 * 3600)
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY no configurado")
    session_id = f"armentaos-{user['id']}-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(api_key=api_key, session_id=session_id, system_message="You are a professional automotive service designer.")
    try:
        chat.with_model("gemini", body.model).with_params(modalities=["image", "text"])
        msg = UserMessage(text=body.prompt)
        text, images = await chat.send_message_multimodal_response(msg)
    except Exception as exc:
        logger.exception("gemini image gen failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Generación falló: {exc}")

    if not images:
        raise HTTPException(status_code=502, detail="El modelo no devolvió imagen")

    first = images[0]
    mime = first.get("mime_type") or "image/png"
    ext = "png" if "png" in mime else "jpg" if "jpeg" in mime or "jpg" in mime else "png"
    image_bytes = _base64.b64decode(first["data"])
    file_id = str(uuid.uuid4())
    path = f"armenta-os/ai/{user['id']}/{file_id}.{ext}"
    try:
        result = put_object(path, image_bytes, mime)
    except Exception as exc:
        logger.exception("storage put failed: %s", exc)
        raise HTTPException(status_code=502, detail="No se pudo guardar la imagen generada")

    doc = {
        "id": file_id,
        "storage_path": result["path"],
        "original_filename": f"ai-{file_id}.{ext}",
        "content_type": mime,
        "size": result.get("size", len(image_bytes)),
        "service_id": body.service_id,
        "uploaded_by": user["id"],
        "is_deleted": False,
        "ai_generated": True,
        "ai_prompt": body.prompt,
        "ai_model": body.model,
        "created_at": now_iso(),
    }
    await db.files.insert_one(doc)
    if body.service_id:
        await db.services.update_one(
            {"id": body.service_id},
            {"$addToSet": {"photos": file_id}, "$set": {"updated_at": now_iso()}},
        )
    return {
        "id": file_id,
        "storage_path": doc["storage_path"],
        "content_type": mime,
        "size": doc["size"],
        "prompt": body.prompt,
        "text_response": text or "",
    }


# ---------------------------------------------------------------------------
# RECIBOS EN PDF
# ---------------------------------------------------------------------------
async def _load_settings_dict() -> dict:
    doc = await db.settings.find_one({"_id": "singleton"}) or {}
    doc.pop("_id", None)
    return {**DEFAULT_SETTINGS, **doc}


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
    if kind == "servicio":
        pays = await db.payments.find({"service_id": doc["id"]}).sort("date", 1).to_list(50)
        out["payments"] = [{"folio": p["folio"], "date": p.get("date"), "method": p.get("method"), "amount": p.get("amount", 0), "reference": p.get("reference", "")} for p in pays]
    if kind == "nota":
        out["client"] = out.get("client") or {"nombre": doc.get("client_name"), "telefono": doc.get("client_phone"), "email": doc.get("client_email")}
        if doc.get("vehicle_label"): out["vehicle"] = {"make": doc["vehicle_label"]}
    return out


RECEIPT_COLLECTIONS = {"servicio": "services", "cotizacion": "quotes", "nota": "notes"}


@api.get("/receipts/pago/{pid}/pdf")
async def payment_receipt_pdf(pid: str, user: dict = Depends(get_current_user)):
    p = await db.payments.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Pago no encontrado")
    ctx = await _payment_context(p)
    settings = await _load_settings_dict()
    pdf_bytes = build_payment_receipt_pdf(ctx, settings)
    filename = f"{p['folio']}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"', "X-Filename": filename})


async def _payment_context(p: dict) -> dict:
    out = _clean_doc(p)
    if isinstance(out.get("created_at"), datetime): out["created_at"] = out["created_at"].isoformat()
    svc = await db.services.find_one({"id": p["service_id"]}) if p.get("service_id") else None
    client_id = p.get("client_id") or (svc or {}).get("client_id")
    if client_id:
        c = await db.clients.find_one({"id": client_id})
        if c: out["client"] = {k: _clean_doc(c).get(k) for k in ("id", "nombre", "telefono", "email", "direccion")}
    if svc:
        out["service"] = {"folio": svc["folio"], "total": svc.get("total", 0), "paid": svc.get("paid", 0), "balance": svc.get("balance", 0), "type": svc.get("type", "")}
        if svc.get("vehicle_id"):
            v = await db.vehicles.find_one({"id": svc["vehicle_id"]})
            if v: out["vehicle"] = " ".join(str(x) for x in (v.get("year"), v.get("make"), v.get("model")) if x)
    return out


@api.post("/payments/{pid}/send-email")
async def send_payment_email(pid: str, user: dict = Depends(require_staff)):
    from html import escape
    from email_service import send_email, EMAIL_FROM_NAME
    p = await db.payments.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Pago no encontrado")
    ctx = await _payment_context(p)
    to = ((ctx.get("client") or {}).get("email") or "").strip()
    if not to:
        raise HTTPException(400, "El cliente no tiene correo registrado")
    settings = await _load_settings_dict()
    cur = settings.get("currency", "MXN")
    svc = ctx.get("service") or {}
    svc_folio = escape(str(svc.get("folio", ""))) if svc else ""
    order_txt = f" aplicado a la orden <strong>{svc_folio}</strong>" if svc else ""
    html = _email_shell(
        settings, "RECIBO DE PAGO", p["folio"],
        f'<p style="margin:0 0 12px">Hola {escape((ctx.get("client") or {}).get("nombre") or "")},</p>'
        f'<p style="margin:0 0 12px">Confirmamos tu pago{order_txt}. Adjuntamos el recibo en PDF.</p>'
        + _kv_table([("Monto", f"${p['amount']:,.2f} {cur}", True), ("Método", escape(str(p.get("method", ""))), False)]
                    + ([("Saldo restante", f"${svc.get('balance', 0):,.2f} {cur}", svc.get("balance", 0) > 0)] if svc else [])),
    )
    email_id = await send_email(to=to, subject=f"Recibo de pago {p['folio']} · {EMAIL_FROM_NAME}", html=html,
                                attachments=[{"filename": f"{p['folio']}.pdf", "bytes": build_payment_receipt_pdf(ctx, settings)}],
                                reply_to=(settings.get("company_email") or None))
    await db.payments.update_one({"id": pid}, {"$set": {"emailed_at": now_iso(), "emailed_to": to}})
    return {"ok": True, "email_id": email_id, "to": to}


def _kv_table(rows):
    from html import escape
    cells = ""
    for i, (k, v, strong) in enumerate(rows):
        border = "border-top:1px solid #e4e4e7;" if i else ""
        color = "color:#dc2626;" if strong is True and k.startswith("Saldo") else ""
        cells += (f'<tr><td style="padding:10px 14px;color:#71717a;{border}">{escape(k)}</td>'
                  f'<td align="right" style="padding:10px 14px;font-weight:bold;{border}{color}">{v}</td></tr>')
    return f'<table role="presentation" width="100%" style="border:1px solid #e4e4e7;border-radius:8px;margin:16px 0">{cells}</table>'


def _email_shell(settings: dict, kicker: str, folio: str, body_html: str) -> str:
    from html import escape
    from email_service import EMAIL_FROM_NAME
    survey_url = (settings.get("survey_url") or "").strip()
    survey_block = (f'<p style="margin:18px 0 0">¿Cómo fue tu servicio? <a href="{escape(survey_url)}" style="color:#dc2626;font-weight:bold">Califícanos en 1 minuto</a>.</p>'
                    if survey_url.startswith("https://") else "")
    return (
        '<table role="presentation" width="100%" style="background:#0a0a0a;padding:24px 0"><tr><td align="center">'
        '<table role="presentation" width="560" style="background:#ffffff;border-radius:12px;font-family:Arial,sans-serif;color:#18181b">'
        '<tr><td style="background:#0a0a0a;color:#fff;padding:20px 28px;border-radius:12px 12px 0 0">'
        f'<div style="font-size:11px;letter-spacing:3px;color:#a1a1aa">{escape(kicker)}</div>'
        f'<div style="font-size:24px;font-weight:bold;margin-top:4px">{escape(folio)}</div></td></tr>'
        f'<tr><td style="padding:24px 28px">{body_html}{survey_block}'
        f'<p style="font-size:12px;color:#888;margin-top:24px">{escape(settings.get("footer_note") or "")}</p>'
        f'<p style="font-size:11px;color:#a1a1aa">Enviado por {escape(EMAIL_FROM_NAME)}. Nunca solicitamos contraseñas ni datos de tarjeta por correo.</p>'
        '</td></tr></table></td></tr></table>'
    )


# ---------------------------------------------------------------------------
# NOTAS DE REMISIÓN (ticket rápido)
# ---------------------------------------------------------------------------
class NoteCreate(BaseModel):
    client_id: Optional[str] = None
    client_name: Optional[str] = ""
    client_phone: Optional[str] = ""
    client_email: Optional[str] = ""
    vehicle_label: Optional[str] = ""
    items: List[QuoteItem] = []
    tax_rate: float = 0.0
    notes: Optional[str] = ""
    paid_amount: float = Field(default=0, ge=0)
    method: PaymentMethod = "cash"


class NoteUpdate(BaseModel):
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    vehicle_label: Optional[str] = None
    items: Optional[List[QuoteItem]] = None
    tax_rate: Optional[float] = None
    notes: Optional[str] = None
    paid_amount: Optional[float] = Field(default=None, ge=0)
    method: Optional[PaymentMethod] = None


class NoteOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    folio: str
    client_id: Optional[str] = None
    client_name: str = ""
    client_phone: str = ""
    client_email: str = ""
    vehicle_label: str = ""
    items: List[QuoteItem] = []
    subtotal: float
    tax_rate: float
    tax: float
    total: float
    paid_amount: float = 0
    balance: float = 0
    method: PaymentMethod = "cash"
    status: str
    notes: str = ""
    created_at: datetime
    updated_at: datetime


def _note_fill(doc: dict):
    subtotal, tax, total, cost, profit = _totals([QuoteItem(**i) if isinstance(i, dict) else i for i in doc.get("items", [])], doc.get("tax_rate", 0))
    paid = round(min(doc.get("paid_amount", 0) or 0, total), 2)
    doc.update({"subtotal": subtotal, "tax": tax, "total": total, "cost_total": cost, "profit": profit,
                "paid_amount": paid, "balance": round(total - paid, 2), "status": "pagada" if total - paid <= 0.001 else "pendiente"})


@api.post("/notes", response_model=NoteOut, status_code=201)
async def create_note(body: NoteCreate, user: dict = Depends(require_staff)):
    doc = body.model_dump()
    doc["items"] = [it.model_dump() for it in body.items]
    if body.client_id:
        c = await db.clients.find_one({"id": body.client_id})
        if c:
            doc["client_name"] = doc["client_name"] or c.get("nombre", "")
            doc["client_phone"] = doc["client_phone"] or c.get("telefono", "")
            doc["client_email"] = doc["client_email"] or c.get("email", "")
    for k in ("client_name", "client_phone", "client_email", "vehicle_label", "notes"):
        doc[k] = (doc.get(k) or "").strip()
    doc["client_name"] = doc["client_name"] or "Público en general"
    _note_fill(doc)
    doc.update({"id": str(uuid.uuid4()), "folio": await _next_folio("NR", db.notes),
                "created_by": user["id"], "created_at": now_iso(), "updated_at": now_iso()})
    await db.notes.insert_one(doc)
    return NoteOut(**_clean_doc(doc))


@api.get("/notes")
async def list_notes(user: dict = Depends(get_current_user), q: Optional[str] = None):
    filt = {"$or": [{"folio": {"$regex": q, "$options": "i"}}, {"client_name": {"$regex": q, "$options": "i"}}]} if q else {}
    docs = await db.notes.find(filt).sort("created_at", -1).limit(300).to_list(300)
    return {"items": [NoteOut(**_clean_doc(d)).model_dump() for d in docs], "total": await db.notes.count_documents(filt)}


@api.get("/notes/{nid}")
async def get_note(nid: str, user: dict = Depends(get_current_user)):
    doc = await db.notes.find_one({"id": nid})
    if not doc: raise HTTPException(404, "Nota no encontrada")
    return await _enrich_doc("nota", doc)


@api.patch("/notes/{nid}", response_model=NoteOut)
async def update_note(nid: str, body: NoteUpdate, user: dict = Depends(require_staff)):
    doc = await db.notes.find_one({"id": nid})
    if not doc: raise HTTPException(404, "Nota no encontrada")
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "items" in upd: upd["items"] = [it.model_dump() for it in body.items]
    doc.update(upd)
    _note_fill(doc)
    doc["updated_at"] = now_iso()
    await db.notes.replace_one({"id": nid}, doc)
    return NoteOut(**_clean_doc(doc))


@api.delete("/notes/{nid}")
async def delete_note(nid: str, user: dict = Depends(require_role("admin", "manager"))):
    r = await db.notes.delete_one({"id": nid})
    if r.deleted_count == 0: raise HTTPException(404, "Nota no encontrada")
    return {"ok": True}


@api.post("/notes/{nid}/send-email")
async def send_note_email(nid: str, user: dict = Depends(require_staff)):
    from html import escape
    from email_service import send_email, EMAIL_FROM_NAME
    doc = await db.notes.find_one({"id": nid})
    if not doc: raise HTTPException(404, "Nota no encontrada")
    to = (doc.get("client_email") or "").strip()
    if not to: raise HTTPException(400, "La nota no tiene correo del cliente")
    settings = await _load_settings_dict()
    cur = settings.get("currency", "MXN")
    enriched = await _enrich_doc("nota", doc)
    html = _email_shell(settings, "NOTA DE REMISIÓN", doc["folio"],
        f'<p style="margin:0 0 12px">Hola {escape(doc.get("client_name") or "")},</p>'
        f'<p style="margin:0 0 12px">Adjuntamos tu nota de remisión en PDF.</p>'
        + _kv_table([("Total", f"${doc.get('total', 0):,.2f} {cur}", True), ("Pagado", f"${doc.get('paid_amount', 0):,.2f} {cur}", False),
                     ("Saldo pendiente", f"${doc.get('balance', 0):,.2f} {cur}", doc.get("balance", 0) > 0)]))
    email_id = await send_email(to=to, subject=f"Nota {doc['folio']} · {EMAIL_FROM_NAME}", html=html,
                                attachments=[{"filename": f"{doc['folio']}.pdf", "bytes": build_receipt_pdf(enriched, settings, kind="nota")}],
                                reply_to=(settings.get("company_email") or None))
    await db.notes.update_one({"id": nid}, {"$set": {"emailed_at": now_iso(), "emailed_to": to}})
    return {"ok": True, "email_id": email_id, "to": to}


@api.get("/receipts/{kind}/{doc_id}/pdf")
async def receipt_pdf(
    kind: str,
    doc_id: str,
    include_photos: bool = Query(True, description="Adjuntar evidencias como anexo"),
    user: dict = Depends(get_current_user),
):
    if kind not in RECEIPT_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Tipo inválido")
    coll = db[RECEIPT_COLLECTIONS[kind]]
    doc = await coll.find_one({"id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    enriched = await _enrich_doc(kind, doc)
    settings = await _load_settings_dict()

    photos_payload = await _service_photos_payload(doc_id) if (kind == "servicio" and include_photos) else None

    pdf_bytes = build_receipt_pdf(enriched, settings, kind=kind, photos=photos_payload)
    filename = f"{enriched.get('folio', 'recibo')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Filename": filename,
        },
    )


async def _service_photos_payload(doc_id: str):
    out = []
    file_docs = await db.files.find({"service_id": doc_id, "is_deleted": False}, {"_id": 0}).sort("created_at", 1).to_list(24)
    for f in file_docs:
        if not (f.get("content_type") or "").startswith("image/"):
            continue
        try:
            data, _ct = get_object(f["storage_path"])
            out.append({"bytes": data, "caption": f.get("original_filename", "")})
        except Exception as exc:
            logger.warning("Photo fetch failed for %s: %s", f.get("id"), exc)
    return out or None


@api.post("/services/{sid}/send-receipt-email")
async def send_service_receipt_email(sid: str, user: dict = Depends(require_staff)):
    from email_service import send_email, EMAIL_FROM_NAME
    doc = await db.services.find_one({"id": sid})
    if not doc:
        raise HTTPException(404, "Servicio no encontrado")
    enriched = await _enrich_doc("servicio", doc)
    client_email = ((enriched.get("client") or {}).get("email") or "").strip()
    if not client_email:
        raise HTTPException(400, "El cliente no tiene correo registrado")
    settings = await _load_settings_dict()
    pdf_bytes = build_receipt_pdf(enriched, settings, kind="servicio", photos=await _service_photos_payload(sid))
    folio = enriched.get("folio", "recibo")
    from html import escape as _esc
    client_name = _esc((enriched.get("client") or {}).get("nombre") or "")
    vehicle = enriched.get("vehicle") or {}
    vehicle_label = _esc(" ".join(str(x) for x in (vehicle.get("year"), vehicle.get("make"), vehicle.get("model")) if x))
    cur = settings.get("currency", "MXN")
    balance = enriched.get("balance", 0) or 0
    html = _email_shell(settings, "ORDEN DE SERVICIO", folio,
        f'<p style="margin:0 0 12px">Hola {client_name},</p>'
        f'<p style="margin:0 0 12px">Adjuntamos el recibo de tu servicio{f" para tu <strong>{vehicle_label}</strong>" if vehicle_label else ""}.</p>'
        + _kv_table([("Total", f"${enriched.get('total', 0):,.2f} {cur}", True), ("Saldo pendiente", f"${balance:,.2f} {cur}", balance > 0)]))
    email_id = await send_email(
        to=client_email,
        subject=f"Recibo {folio} · {EMAIL_FROM_NAME}",
        html=html,
        attachments=[{"filename": f"{folio}.pdf", "bytes": pdf_bytes}],
        reply_to=(settings.get("company_email") or None),
    )
    await db.services.update_one({"id": sid}, {"$set": {"receipt_emailed_at": now_iso(), "receipt_emailed_to": client_email}})
    return {"ok": True, "email_id": email_id, "to": client_email}


# ---------------------------------------------------------------------------
# EQUIPO (usuarios autorizados) — solo admin
# ---------------------------------------------------------------------------
class TeamInvite(BaseModel):
    email: EmailStr
    name: Optional[str] = ""
    role: Role = "technician"


class TeamUpdate(BaseModel):
    role: Optional[Role] = None
    active: Optional[bool] = None
    name: Optional[str] = None


def _team_out(u: dict) -> dict:
    return {"id": u["id"], "email": u.get("email", ""), "name": u.get("name") or u.get("username", ""), "role": u.get("role", "viewer"),
            "active": u.get("active", True), "google_linked": bool(u.get("google_linked")), "last_login_at": u.get("last_login_at"), "created_at": u.get("created_at")}


@api.get("/team")
async def list_team(user: dict = Depends(require_role("admin"))):
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(200)
    return {"items": [_team_out(u) for u in docs]}


@api.post("/team", status_code=201)
async def invite_team(body: TeamInvite, user: dict = Depends(require_role("admin"))):
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Ese correo ya está registrado")
    doc = {"id": str(uuid.uuid4()), "username": email, "email": email, "name": (body.name or "").strip() or email,
           "role": body.role, "active": True, "google_linked": False, "invited_by": user["id"], "created_at": now_iso()}
    await db.users.insert_one(doc)
    return _team_out(doc)


@api.patch("/team/{uid}")
async def update_team(uid: str, body: TeamUpdate, user: dict = Depends(require_role("admin"))):
    target = await db.users.find_one({"id": uid})
    if not target: raise HTTPException(404, "Usuario no encontrado")
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if uid == user["id"] and (upd.get("role") not in (None, "admin") or upd.get("active") is False):
        raise HTTPException(400, "No puedes quitarte tu propio acceso de administrador")
    await db.users.update_one({"id": uid}, {"$set": upd})
    target.update(upd)
    return _team_out(target)


@api.delete("/team/{uid}")
async def delete_team(uid: str, user: dict = Depends(require_role("admin"))):
    if uid == user["id"]: raise HTTPException(400, "No puedes eliminarte a ti mismo")
    r = await db.users.delete_one({"id": uid})
    if r.deleted_count == 0: raise HTTPException(404, "Usuario no encontrado")
    await db.user_sessions.delete_many({"user_id": uid})
    return {"ok": True}


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
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
