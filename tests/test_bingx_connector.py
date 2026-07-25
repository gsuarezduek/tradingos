import pytest
import requests

from tradingos.connectors.bingx import BingxAPIError, get_spot_balances, get_spot_usdt_prices


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
