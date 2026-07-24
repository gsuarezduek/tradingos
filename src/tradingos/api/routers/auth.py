from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.auth.security import create_access_token, hash_password, verify_password
from tradingos.db.models import User
from tradingos.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="la contraseña debe tener al menos 8 caracteres")

    existing = db.query(User).filter(User.email == request.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="ya existe una cuenta con ese email")

    user = User(email=request.email, hashed_password=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == request.email).first()
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="email o contraseña incorrectos")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)
