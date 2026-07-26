from __future__ import annotations

import hashlib
import hmac
import time

import requests

SPOT_BASE_URL = "https://api.binance.com"
FUTURES_USDM_BASE_URL = "https://fapi.binance.com"

_TIMEOUT = 10


class BinanceAPIError(Exception):
    """Error devuelto por Binance (credenciales inválidas, permisos insuficientes, etc.)."""


def _signed_request(
    method: str, base_url: str, path: str, api_key: str, api_secret: str, params: dict[str, str] | None = None
) -> dict | list:
    # Las credenciales solo viven en esta llamada: no se persisten ni se loguean en
    # ningún punto de la cadena (ver POST /brokers/binance/balances en api/main.py).
    all_params = {**(params or {}), "timestamp": str(int(time.time() * 1000))}
    query = "&".join(f"{k}={v}" for k, v in all_params.items())
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{base_url}{path}?{query}&signature={signature}"

    request_fn = requests.get if method == "GET" else requests.post
    try:
        response = request_fn(url, headers={"X-MBX-APIKEY": api_key}, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BinanceAPIError(f"no se pudo conectar con Binance: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("msg", response.text)
        except ValueError:
            detail = response.text
        raise BinanceAPIError(detail)

    return response.json()


def _public_get(url: str) -> dict | list:
    # Endpoint público (sin firma ni API key) — se usa para precios, no para datos
    # de cuenta.
    try:
        response = requests.get(url, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise BinanceAPIError(f"no se pudo conectar con Binance: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("msg", response.text)
        except ValueError:
            detail = response.text
        raise BinanceAPIError(detail)

    return response.json()


def get_spot_usdt_prices() -> dict[str, float]:
    """Último precio de cada par spot cotizado en USDT, indexado por activo base
    (ej. {"BTC": 64399.57, ...}). Público, no requiere credenciales."""
    tickers = _public_get(f"{SPOT_BASE_URL}/api/v3/ticker/price")
    return {t["symbol"][: -len("USDT")]: float(t["price"]) for t in tickers if t["symbol"].endswith("USDT")}


def get_spot_balances(api_key: str, api_secret: str) -> list[dict]:
    """Balances SPOT (free + locked) con saldo mayor a cero."""
    data = _signed_request("GET", SPOT_BASE_URL, "/api/v3/account", api_key, api_secret)
    balances = []
    for b in data["balances"]:
        free, locked = float(b["free"]), float(b["locked"])
        if free > 0 or locked > 0:
            balances.append({"asset": b["asset"], "free": free, "locked": locked, "total": free + locked})
    return balances


def place_market_order(api_key: str, api_secret: str, symbol: str, side: str, amount_usdt: float) -> dict:
    """Envía una orden MARKET spot real gastando (BUY) o liquidando (SELL)
    `amount_usdt` dólares del activo cotizado. Binance soporta `quoteOrderQty` para
    MARKET en ambos lados, así el usuario siempre piensa en USDT sin importar si
    compra o vende — no hace falta convertir a cantidad del activo base acá.
    `newOrderRespType=FULL` (default de Binance para MARKET, se fija explícito para
    no depender de eso) asegura `executedQty`/`cummulativeQuoteQty` en la respuesta,
    con los que se calcula la cantidad y el precio promedio realmente ejecutados."""
    params = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "MARKET",
        "quoteOrderQty": str(amount_usdt),
        "newOrderRespType": "FULL",
    }
    data = _signed_request("POST", SPOT_BASE_URL, "/api/v3/order", api_key, api_secret, params)
    filled_quantity = float(data["executedQty"]) if data.get("executedQty") else None
    quote_quantity = float(data["cummulativeQuoteQty"]) if data.get("cummulativeQuoteQty") else None
    avg_price = quote_quantity / filled_quantity if filled_quantity and quote_quantity else None
    return {
        "exchange_order_id": str(data.get("orderId", "")),
        "raw": data,
        "filled_quantity": filled_quantity,
        "avg_price": avg_price,
    }


def get_futures_usdm_balances(api_key: str, api_secret: str) -> list[dict]:
    """Balances de Futuros USD-M (USDT/BUSD-margined) con saldo mayor a cero."""
    data = _signed_request("GET", FUTURES_USDM_BASE_URL, "/fapi/v2/balance", api_key, api_secret)
    balances = []
    for b in data:
        balance = float(b["balance"])
        if balance > 0:
            balances.append(
                {
                    "asset": b["asset"],
                    "balance": balance,
                    "available_balance": float(b["availableBalance"]),
                    "cross_unrealized_pnl": float(b["crossUnPnl"]),
                }
            )
    return balances
