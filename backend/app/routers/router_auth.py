"""
routers/auth.py
Login endpoint. Issues a JWT token on success.

POST /auth/login
    Body: { "email": "...", "password": "..." }
    Returns: { "access_token": "...", "token_type": "bearer", "name": "..." }
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.auth import verify_password, create_token


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a staff member and return a JWT token.

    The token must be sent in the Authorization header on all protected requests:
        Authorization: Bearer <token>
    """
    # Look up user by email
    row = db.execute(
        text("SELECT name, email, password_hash, role, active FROM users WHERE email = :email"),
        {"email": body.email}
    ).fetchone()

    # Same error message whether email or password is wrong
    # This prevents an attacker from knowing which one failed
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password."
    )

    if not row:
        raise invalid

    if not row.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact your administrator."
        )

    if not verify_password(body.password, row.password_hash):
        raise invalid

    # Update last_login timestamp
    db.execute(
        text("UPDATE users SET last_login = NOW() WHERE email = :email"),
        {"email": body.email}
    )
    db.commit()

    token = create_token(email=row.email, role=row.role)

    return LoginResponse(
        access_token=token,
        name=row.name,
        role=row.role,
    )
