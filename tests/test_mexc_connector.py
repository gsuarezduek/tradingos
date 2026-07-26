import pytest
import requests

from tradingos.connectors.mexc import MexcAPIError, get_spot_balances, get_spot_usdt_prices, place_market_order


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_get_spot_balances_filters_zero_balances(monkeypatch):
    payload = {
        "balances": [
            {"asset": "BTC", "free": "0.5", "locked": "0.0"},
            {"asset": "ETH", "free": "0.0", "locked": "0.0"},
            {"asset": "USDT", "free": "100.0", "locked": "5.0"},
        ]
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
        lambda *a, **k: _FakeResponse(401, {"code": 700002, "msg": "Signature for this request is not valid."}),
    )

    with pytest.raises(MexcAPIError, match="Signature for this request"):
        get_spot_balances("key", "secret")


def test_get_spot_balances_sends_mexc_apikey_header(monkeypatch):
    seen_headers = []

    def _fake_get(url, headers=None, timeout=None):
        seen_headers.append(headers)
        return _FakeResponse(200, {"balances": []})

    monkeypatch.setattr(requests, "get", _fake_get)
    get_spot_balances("my-key", "my-secret")

    assert seen_headers[0] == {"X-MEXC-APIKEY": "my-key"}


def test_get_spot_usdt_prices_filters_and_indexes_by_asset(monkeypatch):
    payload = [
        {"symbol": "BTCUSDT", "price": "64397.84"},
        {"symbol": "METALUSDT", "price": "0.10299"},
        {"symbol": "ETHBTC", "price": "0.02913"},
    ]
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    assert get_spot_usdt_prices() == {"BTC": 64397.84, "METAL": 0.10299}


def test_place_market_order_sends_expected_params(monkeypatch):
    seen = {}

    def _fake_post(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return _FakeResponse(
            200,
            {
                "symbol": "BTCUSDT",
                "orderId": 999,
                "status": "FILLED",
                "executedQty": "0.5",
                "cummulativeQuoteQty": "32250.0",
            },
        )

    monkeypatch.setattr(requests, "post", _fake_post)
    result = place_market_order("my-key", "my-secret", "BTCUSDT", "sell", 32250.0)

    assert seen["headers"] == {"X-MEXC-APIKEY": "my-key"}
    assert "side=SELL" in seen["url"]
    assert "quoteOrderQty=32250.0" in seen["url"]
    assert result == {
        "exchange_order_id": "999",
        "raw": {
            "symbol": "BTCUSDT",
            "orderId": 999,
            "status": "FILLED",
            "executedQty": "0.5",
            "cummulativeQuoteQty": "32250.0",
        },
        "filled_quantity": 0.5,
        "avg_price": 64500.0,
    }


def test_place_market_order_raises_on_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse(400, {"code": 10072, "msg": "Api key info invalid"}))

    with pytest.raises(MexcAPIError, match="Api key info invalid"):
        place_market_order("key", "secret", "BTCUSDT", "buy", 1.0)
