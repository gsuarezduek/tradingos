from __future__ import annotations

import hashlib
import hmac
import time

import requests

SPOT_BASE_URL = "https://api.mexc.com"

_TIMEOUT = 10


class MexcAPIError(Exception):
    """Error devuelto por MEXC (credenciales inválidas, permisos insuficientes, etc.)."""


def _signed_get(path: str, api_key: str, api_secret: str) -> dict | list:
    # Mismo esquema de firma que Binance: HMAC-SHA256 hex de la query string
    # (incluido el timestamp), enviado como header X-MEXC-APIKEY en vez de
    # X-MBX-APIKEY. Las credenciales solo viven en esta llamada, nunca se persisten
    # ni se loguean en ningún punto de la cadena.
    query = f"timestamp={int(time.time() * 1000)}"
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{SPOT_BASE_URL}{path}?{query}&signature={signature}"

    try:
        response = requests.get(url, headers={"X-MEXC-APIKEY": api_key}, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise MexcAPIError(f"no se pudo conectar con MEXC: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("msg", response.text)
        except ValueError:
            detail = response.text
        raise MexcAPIError(detail)

    return response.json()


def get_spot_balances(api_key: str, api_secret: str) -> list[dict]:
    """Balances SPOT (free + locked) con saldo mayor a cero."""
    data = _signed_get("/api/v3/account", api_key, api_secret)
    balances = []
    for b in data["balances"]:
        free, locked = float(b["free"]), float(b["locked"])
        if free > 0 or locked > 0:
            balances.append({"asset": b["asset"], "free": free, "locked": locked, "total": free + locked})
    return balances
