from fastapi.testclient import TestClient

from tradingos.api.main import app
from tradingos.connectors.binance import BinanceAPIError
from tradingos.db.models import LiveOrder
from tradingos.db.session import SessionLocal

client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_connection(token: str, label: str, monkeypatch) -> int:
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    response = client.post(
        "/brokers/binance/connections",
        json={"api_key": "k", "api_secret": "s", "label": label},
        headers=_auth_headers(token),
    )
    return response.json()["id"]


def test_new_connection_starts_with_trading_disabled(monkeypatch):
    token = _register_and_get_token("orders-a@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)

    connections = client.get("/brokers/binance/connections", headers=_auth_headers(token)).json()
    assert connections[0]["trading_enabled"] is False


def test_create_order_rejected_with_403_when_trading_disabled(monkeypatch):
    token = _register_and_get_token("orders-b@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)

    response = client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "BTCUSDT", "side": "buy", "amount_usdt": 10.0},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_toggle_trading_enabled(monkeypatch):
    token = _register_and_get_token("orders-c@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)

    response = client.patch(
        f"/brokers/binance/connections/{connection_id}",
        json={"trading_enabled": True},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["trading_enabled"] is True

    response = client.patch(
        f"/brokers/binance/connections/{connection_id}",
        json={"trading_enabled": False},
        headers=_auth_headers(token),
    )
    assert response.json()["trading_enabled"] is False


def test_create_order_success_persists_live_order(monkeypatch):
    token = _register_and_get_token("orders-d@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)
    client.patch(f"/brokers/binance/connections/{connection_id}", json={"trading_enabled": True}, headers=_auth_headers(token))

    monkeypatch.setattr(
        "tradingos.api.routers.brokers.binance_place_market_order",
        lambda api_key, api_secret, symbol, side, amount_usdt: {
            "exchange_order_id": "42",
            "raw": {"orderId": 42, "status": "FILLED"},
            "filled_quantity": 0.00015,
            "avg_price": 66000.0,
        },
    )

    response = client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "BTCUSDT", "side": "buy", "amount_usdt": 10.0},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["exchange_order_id"] == "42"
    assert body["symbol"] == "BTCUSDT"
    assert body["side"] == "buy"
    assert body["amount_usdt"] == 10.0
    assert body["filled_quantity"] == 0.00015
    assert body["avg_price"] == 66000.0

    db = SessionLocal()
    try:
        order = db.query(LiveOrder).one()
        assert order.status == "submitted"
        assert order.exchange_order_id == "42"
        assert order.raw_response == {"orderId": 42, "status": "FILLED"}
        assert order.amount_usdt == 10.0
        assert order.filled_quantity == 0.00015
        assert order.avg_price == 66000.0
        assert order.user_id is not None
        assert order.broker_connection_id == connection_id
    finally:
        db.close()


def test_create_order_rejected_by_exchange_persists_error(monkeypatch):
    token = _register_and_get_token("orders-e@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)
    client.patch(f"/brokers/binance/connections/{connection_id}", json={"trading_enabled": True}, headers=_auth_headers(token))

    def _raise(api_key, api_secret, symbol, side, amount_usdt):
        raise BinanceAPIError("Account has insufficient balance for requested action.")

    monkeypatch.setattr("tradingos.api.routers.brokers.binance_place_market_order", _raise)

    response = client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "BTCUSDT", "side": "sell", "amount_usdt": 100.0},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert "insufficient balance" in body["error_message"]


def test_create_order_rejects_invalid_side(monkeypatch):
    token = _register_and_get_token("orders-f@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)
    client.patch(f"/brokers/binance/connections/{connection_id}", json={"trading_enabled": True}, headers=_auth_headers(token))

    response = client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "BTCUSDT", "side": "hold", "amount_usdt": 1.0},
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_create_order_rejects_non_positive_amount(monkeypatch):
    token = _register_and_get_token("orders-g@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)
    client.patch(f"/brokers/binance/connections/{connection_id}", json={"trading_enabled": True}, headers=_auth_headers(token))

    response = client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "BTCUSDT", "side": "buy", "amount_usdt": 0},
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_orders_are_isolated_by_ownership(monkeypatch):
    token_a = _register_and_get_token("orders-owner@example.com")
    token_b = _register_and_get_token("orders-other@example.com")
    connection_id = _create_connection(token_a, "cuenta de A", monkeypatch)

    # B no puede togglear trading en la conexión de A.
    response = client.patch(
        f"/brokers/binance/connections/{connection_id}", json={"trading_enabled": True}, headers=_auth_headers(token_b)
    )
    assert response.status_code == 404

    # B tampoco puede ver el historial de órdenes de A.
    response = client.get(f"/brokers/binance/connections/{connection_id}/orders", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_list_orders_returns_most_recent_first(monkeypatch):
    token = _register_and_get_token("orders-h@example.com")
    connection_id = _create_connection(token, "cuenta", monkeypatch)
    client.patch(f"/brokers/binance/connections/{connection_id}", json={"trading_enabled": True}, headers=_auth_headers(token))

    monkeypatch.setattr(
        "tradingos.api.routers.brokers.binance_place_market_order",
        lambda api_key, api_secret, symbol, side, amount_usdt: {"exchange_order_id": "1", "raw": {}, "filled_quantity": None, "avg_price": None},
    )
    client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "BTCUSDT", "side": "buy", "amount_usdt": 10.0},
        headers=_auth_headers(token),
    )
    client.post(
        f"/brokers/binance/connections/{connection_id}/orders",
        json={"symbol": "ETHUSDT", "side": "sell", "amount_usdt": 25.0},
        headers=_auth_headers(token),
    )

    response = client.get(f"/brokers/binance/connections/{connection_id}/orders", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["symbol"] == "ETHUSDT"
    assert body[1]["symbol"] == "BTCUSDT"
