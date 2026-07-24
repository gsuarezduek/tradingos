from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

# Fallback solo para no romper `uvicorn` local sin configurar nada; en producción
# (Railway) JWT_SECRET_KEY siempre está seteada.
_DEV_FALLBACK_SECRET = "dev-only-insecure-secret-do-not-use-in-production"
JWT_SECRET = os.environ.get("JWT_SECRET_KEY", _DEV_FALLBACK_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 60 * 24 * 7  # 7 días


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])
