from fastapi.testclient import TestClient

from tradingos.api.main import app
from tradingos.api.routers import paper_trading as paper_trading_router
from tradingos.db.models import PaperTradingSession
from tradingos.db.session import SessionLocal
from tradingos.strategies.ma_crossover import default_config

client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_payload(symbol: str = "BTCUSDT") -> dict:
    return {"config": default_config(symbol=symbol).model_dump(), "initial_equity": 10_000.0}


def _mock_tick_ok(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.paper_trading.run_tick_for_session", lambda db, session: None)


def test_list_symbols_requires_auth():
    response = client.get("/paper-trading/symbols")
    assert response.status_code == 401


def test_list_symbols_returns_cached_binance_symbols(monkeypatch):
    calls = []

    def _fake_fetch():
        calls.append(1)
        return ["BTCUSDT", "ETHUSDT", "ETHBTC"]

    monkeypatch.setattr("tradingos.api.routers.paper_trading.fetch_spot_symbols", _fake_fetch)
    monkeypatch.setitem(paper_trading_router._symbols_cache, "symbols", None)

    token = _register_and_get_token("symbols@example.com")

    first = client.get("/paper-trading/symbols", headers=_auth_headers(token))
    second = client.get("/paper-trading/symbols", headers=_auth_headers(token))

    assert first.status_code == 200
    assert first.json() == ["BTCUSDT", "ETHUSDT", "ETHBTC"]
    assert second.json() == ["BTCUSDT", "ETHUSDT", "ETHBTC"]
    assert len(calls) == 1  # la segunda llamada usa el cache, no vuelve a pegarle a Binance


def test_create_session_requires_auth():
    response = client.post("/paper-trading/sessions", json=_create_payload())
    assert response.status_code == 401


def test_create_session_rejects_unsupported_timeframe(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tf@example.com")
    payload = _create_payload()
    payload["config"]["timeframe"] = "4h"

    response = client.post("/paper-trading/sessions", json=payload, headers=_auth_headers(token))
    assert response.status_code == 400


def test_create_session_rejects_unknown_strategy(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("strat@example.com")
    payload = _create_payload()
    payload["strategy"] = "no_existe"

    response = client.post("/paper-trading/sessions", json=payload, headers=_auth_headers(token))
    assert response.status_code == 404


def test_create_session_succeeds_and_ticks_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "tradingos.api.routers.paper_trading.run_tick_for_session",
        lambda db, session: calls.append(session.id),
    )
    token = _register_and_get_token("ok@example.com")

    response = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["symbol"] == "BTCUSDT"
    assert calls == [body["id"]]


def test_create_session_does_not_persist_when_first_tick_fails(monkeypatch):
    def _raise(db, session):
        raise RuntimeError("símbolo inválido")

    monkeypatch.setattr("tradingos.api.routers.paper_trading.run_tick_for_session", _raise)
    token = _register_and_get_token("firsttickfail@example.com")

    response = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token))
    assert response.status_code == 400

    db = SessionLocal()
    try:
        assert db.query(PaperTradingSession).count() == 0
    finally:
        db.close()


def test_create_session_allows_multiple_concurrent_active_sessions(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("concurrent@example.com")

    first = client.post("/paper-trading/sessions", json=_create_payload(symbol="BTCUSDT"), headers=_auth_headers(token))
    second = client.post("/paper-trading/sessions", json=_create_payload(symbol="ETHUSDT"), headers=_auth_headers(token))
    assert first.status_code == 200
    assert second.status_code == 200

    listed = client.get("/paper-trading/sessions", headers=_auth_headers(token))
    statuses = {s["id"]: s["status"] for s in listed.json()}
    assert statuses == {first.json()["id"]: "active", second.json()["id"]: "active"}


def test_stop_session_allows_creating_a_new_one(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("restart@example.com")

    first = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token))
    session_id = first.json()["id"]

    stop_response = client.post(f"/paper-trading/sessions/{session_id}/stop", headers=_auth_headers(token))
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    second = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token))
    assert second.status_code == 200


def test_list_sessions_only_returns_own_user(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner@example.com")
    token_b = _register_and_get_token("other@example.com")

    client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token_a))

    response_a = client.get("/paper-trading/sessions", headers=_auth_headers(token_a))
    response_b = client.get("/paper-trading/sessions", headers=_auth_headers(token_b))

    assert len(response_a.json()) == 1
    assert response_b.json() == []


def test_session_detail_includes_equity_curve_and_trades(monkeypatch):
    def _fake_tick(db, session):
        session.current_equity = 10_500.0
        session.equity_curve = [{"timestamp": "2024-01-01T00:00:00+00:00", "equity": 10_500.0}]
        db.commit()

    monkeypatch.setattr("tradingos.api.routers.paper_trading.run_tick_for_session", _fake_tick)
    token = _register_and_get_token("detail@example.com")

    created = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token))
    session_id = created.json()["id"]

    response = client.get(f"/paper-trading/sessions/{session_id}", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["current_equity"] == 10_500.0
    assert body["equity_curve"] == [{"timestamp": "2024-01-01T00:00:00+00:00", "equity": 10_500.0}]
    assert body["trades"] == []


def test_session_response_includes_config(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("config@example.com")

    created = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token))
    assert created.status_code == 200
    assert created.json()["config"]["symbol"] == "BTCUSDT"

    listed = client.get("/paper-trading/sessions", headers=_auth_headers(token))
    assert listed.json()[0]["config"]["symbol"] == "BTCUSDT"


def test_session_detail_for_other_users_session_returns_404(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner2@example.com")
    token_b = _register_and_get_token("other2@example.com")

    created = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token_a))
    session_id = created.json()["id"]

    response = client.get(f"/paper-trading/sessions/{session_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_stop_session_for_other_users_session_returns_404(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner3@example.com")
    token_b = _register_and_get_token("other3@example.com")

    created = client.post("/paper-trading/sessions", json=_create_payload(), headers=_auth_headers(token_a))
    session_id = created.json()["id"]

    response = client.post(f"/paper-trading/sessions/{session_id}/stop", headers=_auth_headers(token_b))
    assert response.status_code == 404
