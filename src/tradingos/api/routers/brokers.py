from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.connectors.binance import BinanceAPIError, get_futures_usdm_balances, get_spot_balances
from tradingos.db import crypto
from tradingos.db.models import BrokerConnection, User
from tradingos.db.session import get_db

router = APIRouter(prefix="/brokers/binance", tags=["brokers"])


def _fetch_section(fetch_fn, api_key: str, api_secret: str) -> dict:
    try:
        return {"ok": True, "balances": fetch_fn(api_key, api_secret)}
    except BinanceAPIError as exc:
        return {"ok": False, "error": str(exc)}


class BinanceCredentials(BaseModel):
    api_key: str
    api_secret: str


@router.post("/balances")
def test_balances(credentials: BinanceCredentials) -> dict:
    """Prueba credenciales sin guardarlas. No requiere estar logueado: se usa para
    validar antes de decidir si conviene crear una conexión persistida."""
    if not credentials.api_key.strip() or not credentials.api_secret.strip():
        raise HTTPException(status_code=400, detail="api_key y api_secret son requeridos")

    return {
        "spot": _fetch_section(get_spot_balances, credentials.api_key, credentials.api_secret),
        "futures_usdm": _fetch_section(get_futures_usdm_balances, credentials.api_key, credentials.api_secret),
    }


class CreateConnectionRequest(BaseModel):
    api_key: str
    api_secret: str
    label: str = "Binance"


class ConnectionResponse(BaseModel):
    id: int
    label: str
    created_at: str


def _to_response(connection: BrokerConnection) -> ConnectionResponse:
    return ConnectionResponse(id=connection.id, label=connection.label, created_at=connection.created_at.isoformat())


@router.post("/connections", response_model=ConnectionResponse)
def create_connection(
    request: CreateConnectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    if not request.api_key.strip() or not request.api_secret.strip():
        raise HTTPException(status_code=400, detail="api_key y api_secret son requeridos")

    # No tiene sentido persistir credenciales que no funcionan.
    try:
        get_spot_balances(request.api_key, request.api_secret)
    except BinanceAPIError as exc:
        raise HTTPException(status_code=400, detail=f"credenciales inválidas: {exc}") from exc

    connection = BrokerConnection(
        user_id=user.id,
        exchange="binance",
        label=request.label,
        api_key_encrypted=crypto.encrypt(request.api_key),
        api_secret_encrypted=crypto.encrypt(request.api_secret),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _to_response(connection)


@router.get("/connections", response_model=list[ConnectionResponse])
def list_connections(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ConnectionResponse]:
    connections = (
        db.query(BrokerConnection)
        .filter(BrokerConnection.user_id == user.id)
        .order_by(BrokerConnection.created_at)
        .all()
    )
    return [_to_response(c) for c in connections]


def _get_owned_connection(connection_id: int, user: User, db: Session) -> BrokerConnection:
    connection = (
        db.query(BrokerConnection)
        .filter(BrokerConnection.id == connection_id, BrokerConnection.user_id == user.id)
        .first()
    )
    if connection is None:
        # 404, no 403: no confirmamos si la conexión existe y es de otro usuario.
        raise HTTPException(status_code=404, detail="conexión no encontrada")
    return connection


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(
    connection_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    connection = _get_owned_connection(connection_id, user, db)
    db.delete(connection)
    db.commit()


@router.get("/connections/{connection_id}/balances")
def connection_balances(
    connection_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    connection = _get_owned_connection(connection_id, user, db)
    api_key = crypto.decrypt(connection.api_key_encrypted)
    api_secret = crypto.decrypt(connection.api_secret_encrypted)
    return {
        "spot": _fetch_section(get_spot_balances, api_key, api_secret),
        "futures_usdm": _fetch_section(get_futures_usdm_balances, api_key, api_secret),
    }
