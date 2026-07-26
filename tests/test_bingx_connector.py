import pytest
import requests

from tradingos.connectors.bingx import BingxAPIError, get_spot_balances, get_spot_usdt_prices, place_market_order


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_get_spot_balances_filters_zero_balances(monkeypatch):
    payload = {
        "code": 0,
        "data": {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                {"asset": "ETH", "free": "0.0", "locked": "0.0"},
                {"asset": "USDT", "free": "100.0", "locked": "5.0"},
            ]
        },
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    balances = get_spot_balances("key", "secret")

    assert balances == [
        {"asset": "BTC", "free": 0.5, "locked": 0.0, "total": 0.5},
        {"asset": "USDT", "free": 100.0, "locked": 5.0, "total": 105.0},
    ]


def test_get_spot_balances_raises_on_invalid_credentials(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **k: _FakeResponse(200, {"code": 100413, "msg": "Incorrect apiKey, please check your valid api key"}),
    )

    with pytest.raises(BingxAPIError, match="Incorrect apiKey"):
        get_spot_balances("key", "secret")


def test_get_spot_balances_sends_bx_apikey_header_and_sorted_signed_query(monkeypatch):
    seen = {}

    def _fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return _FakeResponse(200, {"code": 0, "data": {"balances": []}})

    monkeypatch.setattr(requests, "get", _fake_get)
    get_spot_balances("my-key", "my-secret")

    assert seen["headers"] == {"X-BX-APIKEY": "my-key"}
    assert "signature=" in seen["url"]
    assert "timestamp=" in seen["url"]


def test_get_spot_usdt_prices_filters_and_indexes_by_asset(monkeypatch):
    payload = {
        "code": 0,
        "data": [
            {"symbol": "BTC-USDT", "lastPrice": 64386.67},
            {"symbol": "ETH-USDT", "lastPrice": 1873.69},
            {"symbol": "BTC-USDC", "lastPrice": 64390.0},
        ],
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    assert get_spot_usdt_prices() == {"BTC": 64386.67, "ETH": 1873.69}


def test_place_market_order_translates_symbol_to_hyphenated_form(monkeypatch):
    seen = {}

    def _fake_post(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return _FakeResponse(
            200,
            {
                "code": 0,
                "data": {"orderId": 555, "executedQty": "0.001", "cummulativeQuoteQty": "64.5"},
            },
        )

    monkeypatch.setattr(requests, "post", _fake_post)
    result = place_market_order("my-key", "my-secret", "BTCUSDT", "buy", 10)

    assert seen["headers"] == {"X-BX-APIKEY": "my-key"}
    assert "symbol=BTC-USDT" in seen["url"]
    assert "side=BUY" in seen["url"]
    assert "type=MARKET" in seen["url"]
    assert "quoteOrderQty=10" in seen["url"]
    assert result == {
        "exchange_order_id": "555",
        "raw": {"code": 0, "data": {"orderId": 555, "executedQty": "0.001", "cummulativeQuoteQty": "64.5"}},
        "filled_quantity": 0.001,
        "avg_price": 64500.0,
    }


def test_place_market_order_raises_on_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse(200, {"code": 100413, "msg": "Incorrect apiKey"}))

    with pytest.raises(BingxAPIError, match="Incorrect apiKey"):
        place_market_order("key", "secret", "BTCUSDT", "sell", 1.0)
