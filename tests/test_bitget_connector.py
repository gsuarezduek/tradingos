import base64
import hashlib
import hmac

import pytest
import requests

from tradingos.connectors.bitget import BitgetAPIError, _sign, get_spot_balances, get_spot_usdt_prices, place_market_order


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_sign_matches_documented_algorithm():
    # timestamp + METHOD + requestPath + body, HMAC-SHA256 en base64 (no hex) — la
    # firma de Bitget es distinta a la de Binance/MEXC, se prueba explícitamente.
    expected_prehash = "1700000000000GET/api/v2/spot/account/assets"
    expected = base64.b64encode(hmac.new(b"my-secret", expected_prehash.encode(), hashlib.sha256).digest()).decode()

    signature = _sign("1700000000000", "get", "/api/v2/spot/account/assets", "", "my-secret")

    assert signature == expected


def test_get_spot_balances_filters_zero_balances(monkeypatch):
    payload = {
        "code": "00000",
        "msg": "success",
        "data": [
            {"coin": "BTC", "available": "0.5", "frozen": "0.0"},
            {"coin": "ETH", "available": "0.0", "frozen": "0.0"},
            {"coin": "USDT", "available": "100.0", "frozen": "5.0"},
        ],
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    balances = get_spot_balances("key", "secret", "passphrase")

    assert balances == [
        {"asset": "BTC", "free": 0.5, "locked": 0.0, "total": 0.5},
        {"asset": "USDT", "free": 100.0, "locked": 5.0, "total": 105.0},
    ]


def test_get_spot_balances_raises_when_code_is_not_success(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **k: _FakeResponse(200, {"code": "40012", "msg": "apikey/password is incorrect"}),
    )

    with pytest.raises(BitgetAPIError, match="apikey/password is incorrect"):
        get_spot_balances("key", "secret", "passphrase")


def test_get_spot_balances_sends_required_headers(monkeypatch):
    seen_headers = []

    def _fake_get(url, headers=None, timeout=None):
        seen_headers.append(headers)
        return _FakeResponse(200, {"code": "00000", "data": []})

    monkeypatch.setattr(requests, "get", _fake_get)
    get_spot_balances("my-key", "my-secret", "my-passphrase")

    headers = seen_headers[0]
    assert headers["ACCESS-KEY"] == "my-key"
    assert headers["ACCESS-PASSPHRASE"] == "my-passphrase"
    assert "ACCESS-SIGN" in headers
    assert "ACCESS-TIMESTAMP" in headers


def test_get_spot_usdt_prices_filters_and_indexes_by_asset(monkeypatch):
    payload = {
        "code": "00000",
        "msg": "success",
        "data": [
            {"symbol": "BTCUSDT", "lastPr": "64395.3"},
            {"symbol": "TRXUSDT", "lastPr": "0.33074"},
            {"symbol": "ETHBTC", "lastPr": "0.02913"},
        ],
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    assert get_spot_usdt_prices() == {"BTC": 64395.3, "TRX": 0.33074}


def test_place_market_order_buy_sends_amount_usdt_as_size_directly(monkeypatch):
    # La particularidad real de Bitget: para MARKET BUY, "size" ya es el costo en
    # USDT a gastar, así que el monto se manda tal cual, sin convertir con el precio.
    seen = {}

    def _fake_get(url, headers=None, timeout=None):
        assert "orderInfo" in url
        return _FakeResponse(200, {"code": "00000", "data": [{"baseVolume": "0.002", "priceAvg": "50000"}]})

    def _fake_post(url, headers=None, data=None, timeout=None):
        seen["body"] = data
        seen["headers"] = headers
        return _FakeResponse(200, {"code": "00000", "data": {"orderId": "777"}})

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(requests, "post", _fake_post)

    result = place_market_order("key", "secret", "passphrase", "BTCUSDT", "buy", 100.0)

    assert '"size":"100.0"' in seen["body"]
    assert '"side":"buy"' in seen["body"]
    assert '"orderType":"market"' in seen["body"]
    assert result == {
        "exchange_order_id": "777",
        "raw": {"code": "00000", "data": {"orderId": "777"}},
        "filled_quantity": 0.002,
        "avg_price": 50000.0,
    }


def test_place_market_order_sell_converts_amount_usdt_to_quantity_using_current_price(monkeypatch):
    # Para SELL, "size" sí es la cantidad del activo base — hay que convertir el
    # monto en USDT pedido con el precio spot actual.
    price_payload = {"code": "00000", "data": [{"symbol": "BTCUSDT", "lastPr": "50000"}]}
    order_info_payload = {"code": "00000", "data": [{"baseVolume": "0.001", "priceAvg": "50000"}]}
    seen = {}

    def _fake_get(url, headers=None, timeout=None):
        if "orderInfo" in url:
            return _FakeResponse(200, order_info_payload)
        return _FakeResponse(200, price_payload)

    def _fake_post(url, headers=None, data=None, timeout=None):
        seen["body"] = data
        return _FakeResponse(200, {"code": "00000", "data": {"orderId": "778"}})

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(requests, "post", _fake_post)

    result = place_market_order("key", "secret", "passphrase", "BTCUSDT", "sell", 50.0)

    assert '"size":"0.001"' in seen["body"]
    assert '"side":"sell"' in seen["body"]
    assert result["filled_quantity"] == 0.001
    assert result["avg_price"] == 50000.0


def test_place_market_order_raises_on_error(monkeypatch):
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: _FakeResponse(200, {"code": "40012", "msg": "apikey/password is incorrect"})
    )

    with pytest.raises(BitgetAPIError, match="apikey/password is incorrect"):
        place_market_order("key", "secret", "passphrase", "BTCUSDT", "buy", 1.0)


def test_place_market_order_fill_lookup_failure_does_not_fail_the_order(monkeypatch):
    # La orden ya fue aceptada por Bitget cuando se consulta el fill — si esa
    # segunda llamada falla, la orden se guarda igual, sin cantidad/precio.
    def _fake_get(url, headers=None, timeout=None):
        return _FakeResponse(200, {"code": "40012", "msg": "algo se rompió"})

    def _fake_post(url, headers=None, data=None, timeout=None):
        return _FakeResponse(200, {"code": "00000", "data": {"orderId": "779"}})

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(requests, "post", _fake_post)

    result = place_market_order("key", "secret", "passphrase", "BTCUSDT", "buy", 100.0)

    assert result["exchange_order_id"] == "779"
    assert result["filled_quantity"] is None
    assert result["avg_price"] is None
