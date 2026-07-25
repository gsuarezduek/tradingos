import pytest
import requests

from tradingos.connectors.mexc import MexcAPIError, get_spot_balances


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
