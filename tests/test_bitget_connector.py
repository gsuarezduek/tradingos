import base64
import hashlib
import hmac

import pytest
import requests

from tradingos.connectors.bitget import BitgetAPIError, _sign, get_spot_balances


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
