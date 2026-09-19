from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# other imports below
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid

# ---------------------------------------------------------------------------
# Config & logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("armenta_os")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_HOURS = 24 * 7  # 7 days session per Fase 1 UX


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


# ---------------------------------------------------------------------------
# Mongo
# ---------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="ARMENTA OS API", version="0.1.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    token = None
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def require_role(*roles: str):
    async def _dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return user

    return _dep


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
Role = Literal["admin", "manager", "technician", "assistant", "viewer"]


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    username: str
    email: EmailStr
    name: str
    role: Role
    created_at: datetime


class LoginBody(BaseModel):
    identifier: str = Field(..., min_length=1, description="username o email")
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    token: str
    user: UserPublic
    session_started_at: datetime


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
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

    token = create_access_token(
        user_id=user_doc["id"],
        username=user_doc["username"],
        role=user_doc["role"],
    )
    session_started = datetime.now(timezone.utc)
    await db.users.update_one(
        {"id": user_doc["id"]},
        {"$set": {"last_login_at": session_started.isoformat()}},
    )

    user_doc.pop("_id", None)
    user_doc.pop("password_hash", None)
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])

    return LoginResponse(
        token=token,
        user=UserPublic(**user_doc),
        session_started_at=session_started,
    )


@api.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    if isinstance(user.get("created_at"), str):
        user["created_at"] = datetime.fromisoformat(user["created_at"])
    return UserPublic(**user)


@api.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    # Stateless JWT — client just drops token. Endpoint exists for the client
    # contract and future refresh/session revocation.
    return {"ok": True}


# ---------------------------------------------------------------------------
# Dashboard / stub endpoints (real zero values, no fake data)
# ---------------------------------------------------------------------------
@api.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    # Fase 1: sin datos reales todavía — retornamos ceros reales.
    services_today = await db.services.count_documents(
        {"scheduled_date": datetime.now(timezone.utc).date().isoformat()}
    ) if "services" in await db.list_collection_names() else 0
    quotes_pending = 0
    receivable_total = 0.0
    return {
        "services_today": services_today,
        "quotes_pending": quotes_pending,
        "receivable_total_mxn": receivable_total,
        "system_status": "operativo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@api.get("/health")
async def health():
    return {"status": "ok", "service": "armenta-os", "phase": 1}


# ---------------------------------------------------------------------------
# Startup: indexes + admin seed
# ---------------------------------------------------------------------------
async def ensure_indexes():
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)


async def seed_admin():
    admin_email = os.environ["ADMIN_EMAIL"].strip().lower()
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip().lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    admin_name = os.environ.get("ADMIN_NAME", "Administrador")

    existing = await db.users.find_one({"username": admin_username})
    if existing is None:
        # Also make sure no email collision
        existing = await db.users.find_one({"email": admin_email})

    if existing is None:
        doc = {
            "id": str(uuid.uuid4()),
            "username": admin_username,
            "email": admin_email,
            "name": admin_name,
            "role": "admin",
            "password_hash": hash_password(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login_at": None,
        }
        await db.users.insert_one(doc)
        logger.info("Seeded admin user %s / %s", admin_username, admin_email)
    else:
        # Keep password in sync with env for dev convenience (idempotent).
        if not verify_password(admin_password, existing.get("password_hash", "")):
            await db.users.update_one(
                {"id": existing["id"]},
                {"$set": {"password_hash": hash_password(admin_password)}},
            )
            logger.info("Rotated admin password from env for %s", admin_username)


@app.on_event("startup")
async def _startup():
    await ensure_indexes()
    await seed_admin()


@app.on_event("shutdown")
async def _shutdown():
    client.close()


# ---------------------------------------------------------------------------
# Wire router + CORS
# ---------------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
