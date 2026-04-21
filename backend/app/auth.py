"""
auth.py
JWT token creation and verification.
Password hashing and checking using bcrypt directly.
(passlib has compatibility issues with newer bcrypt versions — bcrypt used directly instead)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.database import get_db


bearer_scheme = HTTPBearer()


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_token(email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": email, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    payload = decode_token(credentials.credentials)
    email = payload.get("sub")

    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    row = db.execute(
        text("SELECT name, email, role, active FROM users WHERE email = :email"),
        {"email": email}
    ).fetchone()

    if not row or not row.active:
        raise HTTPException(status_code=401, detail="User account not found or disabled.")

    return {"name": row.name, "email": row.email, "role": row.role}
