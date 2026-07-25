from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.connectors.binance import (
    BinanceAPIError,
    get_futures_usdm_balances,
    get_spot_balances,
    get_spot_usdt_prices as binance_get_spot_usdt_prices,
)
from tradingos.connectors.bitget import BitgetAPIError
from tradingos.connectors.bitget import get_spot_balances as bitget_get_spot_balances
from tradingos.connectors.bitget import get_spot_usdt_prices as bitget_get_spot_usdt_prices
from tradingos.connectors.mexc import MexcAPIError
from tradingos.connectors.mexc import get_spot_balances as mexc_get_spot_balances
from tradingos.connectors.mexc import get_spot_usdt_prices as mexc_get_spot_usdt_prices
from tradingos.db import crypto
from tradingos.db.models import BrokerConnection, User
from tradingos.db.session import get_db

router = APIRouter(prefix="/brokers/{exchange}", tags=["brokers"])

_APIErrors = (BinanceAPIError, MexcAPIError, BitgetAPIError)

BalanceFn = Callable[[str, str, "str | None"], list[dict]]


def _binance_spot(api_key: str, api_secret: str, passphrase: str | None) -> list[dict]:
    return get_spot_balances(api_key, api_secret)


def _binance_futures(api_key: str, api_secret: str, passphrase: str | None) -> list[dict]:
    return get_futures_usdm_balances(api_key, api_secret)


def _mexc_spot(api_key: str, api_secret: str, passphrase: str | None) -> list[dict]:
    return mexc_get_spot_balances(api_key, api_secret)


def _bitget_spot(api_key: str, api_secret: str, passphrase: str | None) -> list[dict]:
    return bitget_get_spot_balances(api_key, api_secret, passphrase or "")


# Wrappers indirectos (en vez de pasar las funciones importadas directo a
# ExchangeSpec) para que los tests puedan mockear por nombre de módulo, igual que
# con spot_fn/futures_fn de arriba.
def _binance_usdt_prices() -> dict[str, float]:
    return binance_get_spot_usdt_prices()


def _mexc_usdt_prices() -> dict[str, float]:
    return mexc_get_spot_usdt_prices()


def _bitget_usdt_prices() -> dict[str, float]:
    return bitget_get_spot_usdt_prices()


@dataclass(frozen=True)
class ExchangeSpec:
    display_name: str
    spot_fn: BalanceFn
    usdt_prices_fn: Callable[[], dict[str, float]]
    futures_fn: BalanceFn | None = None
    requires_passphrase: bool = False


# Futuros solo soportado para Binance por ahora: los esquemas de firma/endpoints de
# Futuros de MEXC y Bitget son distintos a los de spot y no se confirmaron con la
# misma certeza que spot contra la documentación oficial — agregarlos a ciegas
# arriesga reportar un balance o PnL mal calculado en una integración financiera real.
_EXCHANGES: dict[str, ExchangeSpec] = {
    "binance": ExchangeSpec(
        display_name="Binance", spot_fn=_binance_spot, futures_fn=_binance_futures, usdt_prices_fn=_binance_usdt_prices
    ),
    "mexc": ExchangeSpec(display_name="MEXC", spot_fn=_mexc_spot, usdt_prices_fn=_mexc_usdt_prices),
    "bitget": ExchangeSpec(
        display_name="Bitget", spot_fn=_bitget_spot, requires_passphrase=True, usdt_prices_fn=_bitget_usdt_prices
    ),
}


def _get_exchange_spec(exchange: str) -> ExchangeSpec:
    try:
        return _EXCHANGES[exchange]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"exchange no soportado: {exchange}") from None


def _fetch_section(fetch_fn: BalanceFn, api_key: str, api_secret: str, passphrase: str | None) -> dict:
    try:
        return {"ok": True, "balances": fetch_fn(api_key, api_secret, passphrase)}
    except _APIErrors as exc:
        return {"ok": False, "error": str(exc)}


def _with_usdt_values(balances: list[dict], get_prices: Callable[[], dict[str, float]]) -> dict:
    try:
        prices = get_prices()
    except _APIErrors:
        # No se pudieron obtener precios (falla de red/API pública del exchange) —
        # se listan los balances igual, sin equivalente en USDT en vez de romper.
        return {"balances": [{**b, "usdt_value": None} for b in balances], "usdt_total": None}

    total = 0.0
    enriched = []
    for b in balances:
        if b["asset"] == "USDT":
            value = b["total"]
        else:
            price = prices.get(b["asset"])
            value = b["total"] * price if price is not None else None
        if value is not None:
            total += value
        enriched.append({**b, "usdt_value": value})
    return {"balances": enriched, "usdt_total": total}


def _fetch_balances(spec: ExchangeSpec, api_key: str, api_secret: str, passphrase: str | None) -> dict:
    spot = _fetch_section(spec.spot_fn, api_key, api_secret, passphrase)
    if spot["ok"]:
        spot = {**spot, **_with_usdt_values(spot["balances"], spec.usdt_prices_fn)}
    result = {"spot": spot}
    if spec.futures_fn is not None:
        result["futures_usdm"] = _fetch_section(spec.futures_fn, api_key, api_secret, passphrase)
    return result


class BrokerCredentials(BaseModel):
    api_key: str
    api_secret: str
    passphrase: str | None = None


def _require_credentials(spec: ExchangeSpec, api_key: str, api_secret: str, passphrase: str | None) -> None:
    if not api_key.strip() or not api_secret.strip():
        raise HTTPException(status_code=400, detail="api_key y api_secret son requeridos")
    if spec.requires_passphrase and not (passphrase or "").strip():
        raise HTTPException(status_code=400, detail="passphrase es requerida para este exchange")


@router.post("/balances")
def test_balances(exchange: str, credentials: BrokerCredentials) -> dict:
    """Prueba credenciales sin guardarlas. No requiere estar logueado: se usa para
    validar antes de decidir si conviene crear una conexión persistida."""
    spec = _get_exchange_spec(exchange)
    _require_credentials(spec, credentials.api_key, credentials.api_secret, credentials.passphrase)
    return _fetch_balances(spec, credentials.api_key, credentials.api_secret, credentials.passphrase)


class CreateConnectionRequest(BaseModel):
    api_key: str
    api_secret: str
    passphrase: str | None = None
    label: str = ""


class ConnectionResponse(BaseModel):
    id: int
    exchange: str
    label: str
    created_at: str


def _to_response(connection: BrokerConnection) -> ConnectionResponse:
    return ConnectionResponse(
        id=connection.id, exchange=connection.exchange, label=connection.label, created_at=connection.created_at.isoformat()
    )


@router.post("/connections", response_model=ConnectionResponse)
def create_connection(
    exchange: str,
    request: CreateConnectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    spec = _get_exchange_spec(exchange)
    _require_credentials(spec, request.api_key, request.api_secret, request.passphrase)

    # No tiene sentido persistir credenciales que no funcionan.
    try:
        spec.spot_fn(request.api_key, request.api_secret, request.passphrase)
    except _APIErrors as exc:
        raise HTTPException(status_code=400, detail=f"credenciales inválidas: {exc}") from exc

    connection = BrokerConnection(
        user_id=user.id,
        exchange=exchange,
        label=request.label.strip() or spec.display_name,
        api_key_encrypted=crypto.encrypt(request.api_key),
        api_secret_encrypted=crypto.encrypt(request.api_secret),
        passphrase_encrypted=crypto.encrypt(request.passphrase) if request.passphrase else None,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _to_response(connection)


@router.get("/connections", response_model=list[ConnectionResponse])
def list_connections(exchange: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ConnectionResponse]:
    _get_exchange_spec(exchange)
    connections = (
        db.query(BrokerConnection)
        .filter(BrokerConnection.user_id == user.id, BrokerConnection.exchange == exchange)
        .order_by(BrokerConnection.created_at)
        .all()
    )
    return [_to_response(c) for c in connections]


def _get_owned_connection(exchange: str, connection_id: int, user: User, db: Session) -> BrokerConnection:
    connection = (
        db.query(BrokerConnection)
        .filter(BrokerConnection.id == connection_id, BrokerConnection.user_id == user.id, BrokerConnection.exchange == exchange)
        .first()
    )
    if connection is None:
        # 404, no 403: no confirmamos si la conexión existe y es de otro usuario (o de
        # otro exchange).
        raise HTTPException(status_code=404, detail="conexión no encontrada")
    return connection


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(
    exchange: str, connection_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    connection = _get_owned_connection(exchange, connection_id, user, db)
    db.delete(connection)
    db.commit()


@router.get("/connections/{connection_id}/balances")
def connection_balances(
    exchange: str, connection_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    spec = _get_exchange_spec(exchange)
    connection = _get_owned_connection(exchange, connection_id, user, db)
    api_key = crypto.decrypt(connection.api_key_encrypted)
    api_secret = crypto.decrypt(connection.api_secret_encrypted)
    passphrase = crypto.decrypt(connection.passphrase_encrypted) if connection.passphrase_encrypted else None
    return _fetch_balances(spec, api_key, api_secret, passphrase)
