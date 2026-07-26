from __future__ import annotations

import base64
import hashlib
import hmac
import json
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


def _signed_post(path: str, api_key: str, api_secret: str, passphrase: str, body_dict: dict) -> dict:
    timestamp = str(int(time.time() * 1000))
    body = json.dumps(body_dict, separators=(",", ":"))
    signature = _sign(timestamp, "POST", path, body, api_secret)
    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(f"{BASE_URL}{path}", headers=headers, data=body, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BitgetAPIError(f"no se pudo conectar con Bitget: {exc}") from exc

    try:
        parsed = response.json()
    except ValueError:
        raise BitgetAPIError(response.text) from None

    if parsed.get("code") != "00000":
        raise BitgetAPIError(parsed.get("msg", "error desconocido de Bitget"))

    return parsed


def place_market_order(api_key: str, api_secret: str, passphrase: str, symbol: str, side: str, quantity: float) -> dict:
    """Envía una orden MARKET spot real. `quantity` es la cantidad del activo base
    (misma convención que el resto de los conectores) — Bitget es la excepción
    real: para MARKET BUY, el campo `size` que espera la API es el costo en USDT a
    gastar, no la cantidad del activo base. Se convierte acá adentro con el precio
    spot actual (get_spot_usdt_prices, ya usado para el feature de saldos), así
    esa asimetría no se expone al resto de la app. Para SELL, `size` sí es la
    cantidad del activo base directamente.
    """
    side_lower = side.lower()
    if side_lower == "buy":
        prices = get_spot_usdt_prices()
        asset = symbol[: -len("USDT")] if symbol.endswith("USDT") else symbol
        price = prices.get(asset)
        if price is None:
            raise BitgetAPIError(f"no se encontró precio spot para {asset} contra USDT")
        size = str(quantity * price)
    else:
        size = str(quantity)

    body_dict = {"symbol": symbol, "side": side_lower, "orderType": "market", "force": "gtc", "size": size}
    body = _signed_post("/api/v2/spot/trade/place-order", api_key, api_secret, passphrase, body_dict)
    order_id = body.get("data", {}).get("orderId", "")
    return {"exchange_order_id": str(order_id), "raw": body}
