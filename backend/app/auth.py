"""
auth.py
JWT token creation and verification.
Password hashing and checking.

WHY JWT?
A JWT (JSON Web Token) is a signed string the server gives to the client after login.
The client sends it back on every request. The server verifies the signature to confirm
it is genuine — no database lookup needed on every request.

Token format: header.payload.signature (all base64 encoded)
The payload contains: user email, role, and expiry time.
The signature is created using JWT_SECRET from .env — only our server can create valid tokens.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.database import get_db


# CryptContext handles bcrypt hashing
# bcrypt is the standard for password hashing — slow by design to resist brute force
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTPBearer extracts the token from the Authorization: Bearer <token> header
bearer_scheme = HTTPBearer()


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password. Use this when creating a user."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a stored hash."""
    return pwd_context.verify(plain, hashed)


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_token(email: str, role: str) -> str:
    """
    Create a signed JWT token for a user.
    The token contains the email, role, and expiry time.
    It is signed with JWT_SECRET so only our server can produce valid tokens.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": email,        # subject — who this token is for
        "role": role,
        "exp": expire,       # expiry — jose checks this automatically
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    Raises HTTPException 401 if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
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
    """
    FastAPI dependency that protects any endpoint.
    Extracts the Bearer token, decodes it, and confirms the user still exists
    and is active in the database.

    Usage:
        def my_endpoint(user = Depends(get_current_user)):
            ...user["email"] is available here...
    """
    payload = decode_token(credentials.credentials)
    email = payload.get("sub")

    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    # Confirm user still exists and is active
    row = db.execute(
        text("SELECT name, email, role, active FROM users WHERE email = :email"),
        {"email": email}
    ).fetchone()

    if not row or not row.active:
        raise HTTPException(status_code=401, detail="User account not found or disabled.")

    return {"name": row.name, "email": row.email, "role": row.role}
