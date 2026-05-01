from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import jwt
import bcrypt
import os
from datetime import datetime, timedelta
import database as db
from models import (
    UserCreate, UserUpdate, UserLogin,
    InvoiceCreate, InvoiceUpdate,
    TokenResponse
)

SECRET_KEY = os.getenv("SECRET_KEY", "glambot-georgia-secret-2024-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
security = HTTPBearer()

# Additional origins from env var: FRONTEND_URL=https://yourdomain.ge
_extra = os.getenv("FRONTEND_URL", "")
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://glambot-georgia.netlify.app",
] + ([_extra, _extra.replace("https://", "https://www.")] if _extra else [])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.seed_default_admin()
    yield


app = FastAPI(title="Glambot Georgia API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── AUTH HELPERS ──────────────────────────────────────────

def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(credentials.credentials)


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_manager_or_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    return current_user


# ── AUTH ROUTES ───────────────────────────────────────────

@app.post("/api/auth/login", response_model=TokenResponse)
def login(body: UserLogin):
    user = db.get_user_by_username(body.username)
    if not user or not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["id"], user["username"], user["role"])
    return {
        "token": token,
        "user": {"id": user["id"], "name": user["name"], "username": user["username"], "role": user["role"]}
    }


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = db.get_user_by_id(int(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user["id"], "name": user["name"], "username": user["username"], "role": user["role"]}


# ── USER ROUTES ───────────────────────────────────────────

@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)):
    return db.get_all_users()


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, _: dict = Depends(require_admin)):
    if db.get_user_by_username(body.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user_id = db.create_user(body.name, body.username, pw_hash, body.role)
    return {"id": user_id, "message": "User created"}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, _: dict = Depends(require_admin)):
    if not db.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode() if body.password else None
    db.update_user(user_id, body.name, body.username, pw_hash, body.role)
    return {"message": "User updated"}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, _: dict = Depends(require_admin)):
    if user_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete primary admin")
    if not db.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    db.delete_user(user_id)
    return {"message": "User deleted"}


# ── INVOICE ROUTES ────────────────────────────────────────

@app.get("/api/invoices")
def list_invoices(_: dict = Depends(get_current_user)):
    return db.get_all_invoices()


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, _: dict = Depends(get_current_user)):
    inv = db.get_invoice_by_id(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@app.post("/api/invoices", status_code=201)
def create_invoice(body: InvoiceCreate, current_user: dict = Depends(require_manager_or_admin)):
    inv_id = db.create_invoice(body, int(current_user["sub"]))
    return {"id": inv_id, "message": "Invoice created"}


@app.put("/api/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: InvoiceUpdate, _: dict = Depends(require_manager_or_admin)):
    if not db.get_invoice_by_id(invoice_id):
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.update_invoice(invoice_id, body)
    return {"message": "Invoice updated"}


@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, _: dict = Depends(require_admin)):
    if not db.get_invoice_by_id(invoice_id):
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete_invoice(invoice_id)
    return {"message": "Invoice deleted"}


@app.get("/api/stats")
def get_stats(_: dict = Depends(get_current_user)):
    return db.get_stats()
