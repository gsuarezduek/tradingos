from fastapi.testclient import TestClient

from tradingos.api.main import app
from tradingos.connectors.binance import BinanceAPIError
from tradingos.db.models import BrokerConnection
from tradingos.db.session import SessionLocal

client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_test_balances_returns_ok_sections_without_saving(monkeypatch):
    monkeypatch.setattr(
        "tradingos.api.routers.brokers.get_spot_balances",
        lambda api_key, api_secret: [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0}],
    )
    monkeypatch.setattr("tradingos.api.routers.brokers.binance_get_spot_usdt_prices", lambda: {"BTC": 50000.0})
    monkeypatch.setattr(
        "tradingos.api.routers.brokers.get_futures_usdm_balances",
        lambda api_key, api_secret: [{"asset": "USDT", "balance": 10.0, "available_balance": 10.0, "cross_unrealized_pnl": 0.0}],
    )
    response = client.post("/brokers/binance/balances", json={"api_key": "k", "api_secret": "s"})
    assert response.status_code == 200
    body = response.json()
    assert body["spot"] == {
        "ok": True,
        "balances": [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0, "usdt_value": 50000.0}],
        "usdt_total": 50000.0,
    }
    assert body["futures_usdm"]["ok"] is True

    db = SessionLocal()
    try:
        assert db.query(BrokerConnection).count() == 0
    finally:
        db.close()


def test_test_balances_reports_per_section_error(monkeypatch):
    def _raise(api_key, api_secret):
        raise BinanceAPIError("Invalid API-key, IP, or permissions for action.")

    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", _raise)
    monkeypatch.setattr("tradingos.api.routers.brokers.get_futures_usdm_balances", lambda api_key, api_secret: [])

    response = client.post("/brokers/binance/balances", json={"api_key": "bad", "api_secret": "bad"})
    assert response.status_code == 200
    body = response.json()
    assert body["spot"] == {"ok": False, "error": "Invalid API-key, IP, or permissions for action."}
    assert body["futures_usdm"] == {"ok": True, "balances": []}


def test_test_balances_rejects_empty_credentials():
    response = client.post("/brokers/binance/balances", json={"api_key": "", "api_secret": ""})
    assert response.status_code == 400


def test_create_connection_requires_auth():
    response = client.post("/brokers/binance/connections", json={"api_key": "k", "api_secret": "s"})
    assert response.status_code == 401


def test_create_connection_validates_credentials_before_saving(monkeypatch):
    def _raise(api_key, api_secret):
        raise BinanceAPIError("bad key")

    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", _raise)
    token = _register_and_get_token("f@example.com")

    response = client.post(
        "/brokers/binance/connections",
        json={"api_key": "bad", "api_secret": "bad", "label": "Test"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 400

    db = SessionLocal()
    try:
        assert db.query(BrokerConnection).count() == 0
    finally:
        db.close()


def test_create_connection_persists_encrypted_not_plaintext(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    token = _register_and_get_token("g@example.com")

    response = client.post(
        "/brokers/binance/connections",
        json={"api_key": "my-real-key", "api_secret": "my-real-secret", "label": "Cuenta principal"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "Cuenta principal"
    assert "api_key" not in body
    assert "api_secret" not in body

    db = SessionLocal()
    try:
        connection = db.query(BrokerConnection).one()
        assert connection.api_key_encrypted != "my-real-key"
        assert connection.api_secret_encrypted != "my-real-secret"
        assert "my-real-key" not in connection.api_key_encrypted
    finally:
        db.close()


def test_list_connections_only_returns_own_user(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    token_a = _register_and_get_token("owner@example.com")
    token_b = _register_and_get_token("other@example.com")

    client.post(
        "/brokers/binance/connections",
        json={"api_key": "k", "api_secret": "s", "label": "De A"},
        headers=_auth_headers(token_a),
    )

    response_a = client.get("/brokers/binance/connections", headers=_auth_headers(token_a))
    response_b = client.get("/brokers/binance/connections", headers=_auth_headers(token_b))

    assert len(response_a.json()) == 1
    assert response_a.json()[0]["label"] == "De A"
    assert response_b.json() == []


def test_delete_connection_of_another_user_returns_404(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    token_a = _register_and_get_token("owner2@example.com")
    token_b = _register_and_get_token("other2@example.com")

    created = client.post(
        "/brokers/binance/connections",
        json={"api_key": "k", "api_secret": "s", "label": "De A"},
        headers=_auth_headers(token_a),
    )
    connection_id = created.json()["id"]

    response = client.delete(f"/brokers/binance/connections/{connection_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_delete_connection_removes_it(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    token = _register_and_get_token("h@example.com")

    created = client.post(
        "/brokers/binance/connections",
        json={"api_key": "k", "api_secret": "s", "label": "Borrar"},
        headers=_auth_headers(token),
    )
    connection_id = created.json()["id"]

    delete_response = client.delete(f"/brokers/binance/connections/{connection_id}", headers=_auth_headers(token))
    assert delete_response.status_code == 204

    list_response = client.get("/brokers/binance/connections", headers=_auth_headers(token))
    assert list_response.json() == []


def test_connection_balances_decrypts_and_calls_connector(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    token = _register_and_get_token("i@example.com")

    created = client.post(
        "/brokers/binance/connections",
        json={"api_key": "real-key", "api_secret": "real-secret", "label": "Saldos"},
        headers=_auth_headers(token),
    )
    connection_id = created.json()["id"]

    seen_credentials = []

    def _fake_spot(api_key, api_secret):
        seen_credentials.append((api_key, api_secret))
        return [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0}]

    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", _fake_spot)
    monkeypatch.setattr("tradingos.api.routers.brokers.get_futures_usdm_balances", lambda api_key, api_secret: [])
    monkeypatch.setattr("tradingos.api.routers.brokers.binance_get_spot_usdt_prices", lambda: {"BTC": 50000.0})

    response = client.get(f"/brokers/binance/connections/{connection_id}/balances", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["spot"]["ok"] is True
    assert body["spot"]["balances"][0]["asset"] == "BTC"
    assert body["spot"]["balances"][0]["usdt_value"] == 50000.0
    assert body["spot"]["usdt_total"] == 50000.0
    assert seen_credentials == [("real-key", "real-secret")]


def test_connection_balances_for_missing_connection_returns_404():
    token = _register_and_get_token("j@example.com")
    response = client.get("/brokers/binance/connections/999/balances", headers=_auth_headers(token))
    assert response.status_code == 404


def test_test_balances_usdt_value_is_null_when_asset_has_no_price(monkeypatch):
    monkeypatch.setattr(
        "tradingos.api.routers.brokers.get_spot_balances",
        lambda api_key, api_secret: [
            {"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0},
            {"asset": "SOMEOBSCURECOIN", "free": 2.0, "locked": 0.0, "total": 2.0},
        ],
    )
    monkeypatch.setattr("tradingos.api.routers.brokers.binance_get_spot_usdt_prices", lambda: {"BTC": 50000.0})
    monkeypatch.setattr("tradingos.api.routers.brokers.get_futures_usdm_balances", lambda api_key, api_secret: [])

    response = client.post("/brokers/binance/balances", json={"api_key": "k", "api_secret": "s"})
    body = response.json()
    assert body["spot"]["balances"][0]["usdt_value"] == 50000.0
    assert body["spot"]["balances"][1]["usdt_value"] is None
    assert body["spot"]["usdt_total"] == 50000.0  # el activo sin precio no entra en la suma


def test_test_balances_usdt_total_is_null_when_price_endpoint_fails(monkeypatch):
    def _raise_prices():
        raise BinanceAPIError("no se pudo conectar con Binance: timeout")

    monkeypatch.setattr(
        "tradingos.api.routers.brokers.get_spot_balances",
        lambda api_key, api_secret: [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0}],
    )
    monkeypatch.setattr("tradingos.api.routers.brokers.binance_get_spot_usdt_prices", _raise_prices)
    monkeypatch.setattr("tradingos.api.routers.brokers.get_futures_usdm_balances", lambda api_key, api_secret: [])

    response = client.post("/brokers/binance/balances", json={"api_key": "k", "api_secret": "s"})
    assert response.status_code == 200
    body = response.json()
    assert body["spot"]["ok"] is True
    assert body["spot"]["balances"][0]["usdt_value"] is None
    assert body["spot"]["usdt_total"] is None


def test_unsupported_exchange_returns_404():
    response = client.post("/brokers/kraken/balances", json={"api_key": "k", "api_secret": "s"})
    assert response.status_code == 404


def test_mexc_test_balances_returns_ok_section_without_saving(monkeypatch):
    monkeypatch.setattr(
        "tradingos.api.routers.brokers.mexc_get_spot_balances",
        lambda api_key, api_secret: [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0}],
    )
    monkeypatch.setattr("tradingos.api.routers.brokers.mexc_get_spot_usdt_prices", lambda: {"BTC": 50000.0})
    response = client.post("/brokers/mexc/balances", json={"api_key": "k", "api_secret": "s"})
    assert response.status_code == 200
    body = response.json()
    assert body["spot"] == {
        "ok": True,
        "balances": [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0, "usdt_value": 50000.0}],
        "usdt_total": 50000.0,
    }
    assert "futures_usdm" not in body

    db = SessionLocal()
    try:
        assert db.query(BrokerConnection).count() == 0
    finally:
        db.close()


def test_mexc_create_connection_persists_with_exchange_field(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.mexc_get_spot_balances", lambda api_key, api_secret: [])
    token = _register_and_get_token("mexc-user@example.com")

    response = client.post(
        "/brokers/mexc/connections",
        json={"api_key": "k", "api_secret": "s", "label": "Mi cuenta MEXC"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["exchange"] == "mexc"
    assert body["label"] == "Mi cuenta MEXC"


def test_mexc_connections_are_isolated_from_binance_connections(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.mexc_get_spot_balances", lambda api_key, api_secret: [])
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    token = _register_and_get_token("multi-exchange@example.com")

    client.post("/brokers/mexc/connections", json={"api_key": "k", "api_secret": "s"}, headers=_auth_headers(token))
    client.post("/brokers/binance/connections", json={"api_key": "k", "api_secret": "s"}, headers=_auth_headers(token))

    mexc_connections = client.get("/brokers/mexc/connections", headers=_auth_headers(token)).json()
    binance_connections = client.get("/brokers/binance/connections", headers=_auth_headers(token)).json()

    assert len(mexc_connections) == 1
    assert len(binance_connections) == 1
    assert mexc_connections[0]["exchange"] == "mexc"
    assert binance_connections[0]["exchange"] == "binance"


def test_bitget_requires_passphrase_to_create_connection(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.bitget_get_spot_balances", lambda api_key, api_secret, passphrase: [])
    token = _register_and_get_token("bitget-nopass@example.com")

    response = client.post(
        "/brokers/bitget/connections",
        json={"api_key": "k", "api_secret": "s"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_bitget_create_connection_persists_encrypted_passphrase(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.bitget_get_spot_balances", lambda api_key, api_secret, passphrase: [])
    token = _register_and_get_token("bitget-user@example.com")

    response = client.post(
        "/brokers/bitget/connections",
        json={"api_key": "k", "api_secret": "s", "passphrase": "my-real-passphrase", "label": "Bitget"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["exchange"] == "bitget"

    db = SessionLocal()
    try:
        connection = db.query(BrokerConnection).filter(BrokerConnection.exchange == "bitget").one()
        assert connection.passphrase_encrypted is not None
        assert connection.passphrase_encrypted != "my-real-passphrase"
    finally:
        db.close()


def test_bitget_connection_balances_decrypts_passphrase(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.brokers.bitget_get_spot_balances", lambda api_key, api_secret, passphrase: [])
    token = _register_and_get_token("bitget-balances@example.com")

    created = client.post(
        "/brokers/bitget/connections",
        json={"api_key": "real-key", "api_secret": "real-secret", "passphrase": "real-pass", "label": "Saldos"},
        headers=_auth_headers(token),
    )
    connection_id = created.json()["id"]

    seen_credentials = []

    def _fake_spot(api_key, api_secret, passphrase):
        seen_credentials.append((api_key, api_secret, passphrase))
        return [{"asset": "BTC", "free": 1.0, "locked": 0.0, "total": 1.0}]

    monkeypatch.setattr("tradingos.api.routers.brokers.bitget_get_spot_balances", _fake_spot)
    monkeypatch.setattr("tradingos.api.routers.brokers.bitget_get_spot_usdt_prices", lambda: {"BTC": 50000.0})

    response = client.get(f"/brokers/bitget/connections/{connection_id}/balances", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["spot"]["ok"] is True
    assert body["spot"]["balances"][0]["usdt_value"] == 50000.0
    assert body["spot"]["usdt_total"] == 50000.0
    assert "futures_usdm" not in body
    assert seen_credentials == [("real-key", "real-secret", "real-pass")]
