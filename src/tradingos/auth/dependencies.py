from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from tradingos.auth.security import decode_access_token
from tradingos.db.models import User
from tradingos.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="no autenticado")

    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="token inválido o expirado") from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="usuario no encontrado")
    return user
