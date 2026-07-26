from __future__ import annotations

import hashlib
import hmac
import time

import requests

BASE_URL = "https://open-api.bingx.com"

_TIMEOUT = 10


class BingxAPIError(Exception):
    """Error devuelto por BingX (credenciales inválidas, permisos insuficientes, etc.)."""


def _sign(params: dict[str, str], api_secret: str) -> tuple[str, str]:
    # BingX firma la query string completa ordenada alfabéticamente por clave
    # (a diferencia de Binance/MEXC, que solo firman timestamp) — HMAC-SHA256 hex.
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return query, signature


def _signed_request(method: str, path: str, api_key: str, api_secret: str, extra_params: dict[str, str] | None = None) -> dict:
    params = {**(extra_params or {}), "timestamp": str(int(time.time() * 1000))}
    query, signature = _sign(params, api_secret)
    url = f"{BASE_URL}{path}?{query}&signature={signature}"

    request_fn = requests.get if method == "GET" else requests.post
    try:
        response = request_fn(url, headers={"X-BX-APIKEY": api_key}, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BingxAPIError(f"no se pudo conectar con BingX: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        raise BingxAPIError(response.text) from None

    if body.get("code") != 0:
        raise BingxAPIError(body.get("msg", "error desconocido de BingX"))

    return body


def _public_get(url: str) -> dict:
    # Endpoint público (sin firma ni API key) — se usa para precios, no para datos
    # de cuenta. Misma envoltura {code, data} que los endpoints firmados.
    try:
        response = requests.get(url, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BingxAPIError(f"no se pudo conectar con BingX: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        raise BingxAPIError(response.text) from None

    if body.get("code") != 0:
        raise BingxAPIError(body.get("msg", "error desconocido de BingX"))

    return body


def get_spot_balances(api_key: str, api_secret: str) -> list[dict]:
    """Balances SPOT (free + locked) con saldo mayor a cero."""
    body = _signed_request("GET", "/openApi/spot/v1/account/balance", api_key, api_secret)
    balances = []
    for b in body["data"]["balances"]:
        free, locked = float(b["free"]), float(b["locked"])
        if free > 0 or locked > 0:
            balances.append({"asset": b["asset"], "free": free, "locked": locked, "total": free + locked})
    return balances


def place_market_order(api_key: str, api_secret: str, symbol: str, side: str, quantity: float) -> dict:
    """Envía una orden MARKET spot real. `quantity` es la cantidad del activo base
    (sirve igual para compra y venta). `symbol` viene concatenado (ej. "BTCUSDT",
    misma convención que el resto de la app) — BingX necesita el guion, se traduce
    acá adentro (ej. "BTC-USDT"), no se expone hacia afuera."""
    bingx_symbol = f"{symbol[:-len('USDT')]}-USDT" if symbol.endswith("USDT") else symbol
    params = {"symbol": bingx_symbol, "side": side.upper(), "type": "MARKET", "quantity": str(quantity)}
    body = _signed_request("POST", "/openApi/spot/v1/trade/order", api_key, api_secret, params)
    order_id = body.get("data", {}).get("orderId", "")
    return {"exchange_order_id": str(order_id), "raw": body}


def get_spot_usdt_prices() -> dict[str, float]:
    """Último precio de cada par spot cotizado en USDT, indexado por activo base
    (ej. {"BTC": 64386.67, ...}). Público, no requiere credenciales."""
    body = _public_get(f"{BASE_URL}/openApi/spot/v1/ticker/24hr")
    return {t["symbol"][: -len("-USDT")]: float(t["lastPrice"]) for t in body["data"] if t["symbol"].endswith("-USDT")}
