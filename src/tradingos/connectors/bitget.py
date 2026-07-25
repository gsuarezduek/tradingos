from __future__ import annotations

import base64
import hashlib
import hmac
import time

import requests

BASE_URL = "https://api.bitget.com"

_TIMEOUT = 10


class BitgetAPIError(Exception):
    """Error devuelto por Bitget (credenciales inválidas, permisos insuficientes, etc.)."""


def _sign(timestamp: str, method: str, request_path: str, body: str, api_secret: str) -> str:
    # Firma de Bitget (distinta a Binance/MEXC): HMAC-SHA256 en base64, no hex, y el
    # mensaje incluye método + path + body en vez de solo la query string. Para un GET
    # sin query params el body se omite del mensaje (documentado así por Bitget).
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _signed_get(path: str, api_key: str, api_secret: str, passphrase: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    signature = _sign(timestamp, "GET", path, "", api_secret)
    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BitgetAPIError(f"no se pudo conectar con Bitget: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        raise BitgetAPIError(response.text) from None

    if body.get("code") != "00000":
        raise BitgetAPIError(body.get("msg", "error desconocido de Bitget"))

    return body


def _public_get(url: str) -> dict:
    # Endpoint público (sin firma ni API key) — se usa para precios, no para datos
    # de cuenta. Misma envoltura {code, msg, data} que los endpoints firmados.
    try:
        response = requests.get(url, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BitgetAPIError(f"no se pudo conectar con Bitget: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        raise BitgetAPIError(response.text) from None

    if body.get("code") != "00000":
        raise BitgetAPIError(body.get("msg", "error desconocido de Bitget"))

    return body


def get_spot_usdt_prices() -> dict[str, float]:
    """Último precio de cada par spot cotizado en USDT, indexado por activo base
    (ej. {"BTC": 64395.3, ...}). Público, no requiere credenciales."""
    body = _public_get(f"{BASE_URL}/api/v2/spot/market/tickers")
    return {t["symbol"][: -len("USDT")]: float(t["lastPr"]) for t in body["data"] if t["symbol"].endswith("USDT")}


def get_spot_balances(api_key: str, api_secret: str, passphrase: str) -> list[dict]:
    """Balances SPOT (available + frozen) con saldo mayor a cero."""
    body = _signed_get("/api/v2/spot/account/assets", api_key, api_secret, passphrase)
    balances = []
    for b in body["data"]:
        free, locked = float(b["available"]), float(b["frozen"])
        if free > 0 or locked > 0:
            balances.append({"asset": b["coin"], "free": free, "locked": locked, "total": free + locked})
    return balances
