from __future__ import annotations

import hashlib
import hmac
import time

import requests

SPOT_BASE_URL = "https://api.mexc.com"

_TIMEOUT = 10


class MexcAPIError(Exception):
    """Error devuelto por MEXC (credenciales inválidas, permisos insuficientes, etc.)."""


def _signed_request(method: str, path: str, api_key: str, api_secret: str, params: dict[str, str] | None = None) -> dict | list:
    # Mismo esquema de firma que Binance: HMAC-SHA256 hex de la query string
    # (incluido el timestamp), enviado como header X-MEXC-APIKEY en vez de
    # X-MBX-APIKEY. Las credenciales solo viven en esta llamada, nunca se persisten
    # ni se loguean en ningún punto de la cadena.
    all_params = {**(params or {}), "timestamp": str(int(time.time() * 1000))}
    query = "&".join(f"{k}={v}" for k, v in all_params.items())
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{SPOT_BASE_URL}{path}?{query}&signature={signature}"

    request_fn = requests.get if method == "GET" else requests.post
    try:
        response = request_fn(url, headers={"X-MEXC-APIKEY": api_key}, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise MexcAPIError(f"no se pudo conectar con MEXC: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("msg", response.text)
        except ValueError:
            detail = response.text
        raise MexcAPIError(detail)

    return response.json()


def _public_get(url: str) -> dict | list:
    # Endpoint público (sin firma ni API key) — se usa para precios, no para datos
    # de cuenta.
    try:
        response = requests.get(url, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise MexcAPIError(f"no se pudo conectar con MEXC: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("msg", response.text)
        except ValueError:
            detail = response.text
        raise MexcAPIError(detail)

    return response.json()


def get_spot_usdt_prices() -> dict[str, float]:
    """Último precio de cada par spot cotizado en USDT, indexado por activo base
    (ej. {"BTC": 64397.84, ...}). Público, no requiere credenciales."""
    tickers = _public_get(f"{SPOT_BASE_URL}/api/v3/ticker/price")
    return {t["symbol"][: -len("USDT")]: float(t["price"]) for t in tickers if t["symbol"].endswith("USDT")}


def get_spot_balances(api_key: str, api_secret: str) -> list[dict]:
    """Balances SPOT (free + locked) con saldo mayor a cero."""
    data = _signed_request("GET", "/api/v3/account", api_key, api_secret)
    balances = []
    for b in data["balances"]:
        free, locked = float(b["free"]), float(b["locked"])
        if free > 0 or locked > 0:
            balances.append({"asset": b["asset"], "free": free, "locked": locked, "total": free + locked})
    return balances


def place_market_order(api_key: str, api_secret: str, symbol: str, side: str, quantity: float) -> dict:
    """Envía una orden MARKET spot real. `quantity` es la cantidad del activo base
    (mismo esquema que Binance, sirve igual para compra y venta)."""
    params = {"symbol": symbol, "side": side.upper(), "type": "MARKET", "quantity": str(quantity)}
    data = _signed_request("POST", "/api/v3/order", api_key, api_secret, params)
    return {"exchange_order_id": str(data.get("orderId", "")), "raw": data}
