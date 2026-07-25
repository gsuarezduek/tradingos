import pytest
import requests

from tradingos.connectors.binance import (
    BinanceAPIError,
    get_futures_usdm_balances,
    get_spot_balances,
    get_spot_usdt_prices,
)


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
        lambda *a, **k: _FakeResponse(401, {"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."}),
    )

    with pytest.raises(BinanceAPIError, match="Invalid API-key"):
        get_spot_balances("key", "secret")


def test_get_futures_usdm_balances_filters_zero_balances(monkeypatch):
    payload = [
        {"asset": "USDT", "balance": "50.0", "availableBalance": "40.0", "crossUnPnl": "1.5"},
        {"asset": "BUSD", "balance": "0.0", "availableBalance": "0.0", "crossUnPnl": "0.0"},
    ]
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    balances = get_futures_usdm_balances("key", "secret")

    assert balances == [
        {"asset": "USDT", "balance": 50.0, "available_balance": 40.0, "cross_unrealized_pnl": 1.5},
    ]


def test_get_spot_usdt_prices_filters_and_indexes_by_asset(monkeypatch):
    payload = [
        {"symbol": "BTCUSDT", "price": "64399.57"},
        {"symbol": "ETHBTC", "price": "0.02913000"},
        {"symbol": "ETHUSDT", "price": "3200.5"},
    ]
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    assert get_spot_usdt_prices() == {"BTC": 64399.57, "ETH": 3200.5}
