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


def _create_strategy(token: str, **overrides) -> dict:
    """Crea una SavedStrategy real (corre un backtest de verdad contra el dataset de
    BTCUSDT_1h) — paper trading siempre parte de una de estas, no de una config suelta."""
    payload = {
        "name": "Mi EMA Crossover",
        "strategy_type": "ma_crossover",
        "category": "swing",
        "symbols": ["BTCUSDT"],
        "timeframes": ["1h"],
        "config": default_config(symbol="BTCUSDT", timeframe="1h").model_dump(),
        "notes": "",
        "initial_equity": 10_000.0,
    }
    payload.update(overrides)
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))
    assert response.status_code == 200, response.json()
    return response.json()


def _session_payload(strategy_id: int, *, symbol: str = "BTCUSDT", timeframe: str = "1h") -> dict:
    return {"strategy_id": strategy_id, "symbol": symbol, "timeframe": timeframe, "initial_equity": 10_000.0}


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
    response = client.post("/paper-trading/sessions", json=_session_payload(strategy_id=1))
    assert response.status_code == 401


def test_create_session_rejects_unknown_strategy_id(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("strat@example.com")

    response = client.post("/paper-trading/sessions", json=_session_payload(strategy_id=999_999), headers=_auth_headers(token))
    assert response.status_code == 404


def test_create_session_rejects_another_users_strategy(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner-strat@example.com")
    token_b = _register_and_get_token("other-strat@example.com")
    strategy = _create_strategy(token_a)

    response = client.post(
        "/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token_b)
    )
    assert response.status_code == 404


def test_create_session_rejects_unsupported_timeframe(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tf@example.com")
    strategy = _create_strategy(token, timeframes=["1h", "4h"])

    response = client.post(
        "/paper-trading/sessions",
        json=_session_payload(strategy["id"], timeframe="4h"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_create_session_rejects_symbol_not_declared_by_strategy(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("symbolnotdeclared@example.com")
    strategy = _create_strategy(token)  # symbols=["BTCUSDT"]

    response = client.post(
        "/paper-trading/sessions",
        json=_session_payload(strategy["id"], symbol="SOLUSDT"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400
    assert "SOLUSDT" in response.json()["detail"]


def test_create_session_succeeds_and_ticks_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "tradingos.api.routers.paper_trading.run_tick_for_session",
        lambda db, session: calls.append(session.id),
    )
    token = _register_and_get_token("ok@example.com")
    strategy = _create_strategy(token)

    response = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["symbol"] == "BTCUSDT"
    assert body["strategy_id"] == strategy["id"]
    assert body["strategy_name"] == strategy["name"]
    assert calls == [body["id"]]


def test_create_session_overrides_symbol_from_strategy_config(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("override@example.com")
    strategy = _create_strategy(token, symbols=["BTCUSDT", "ETHUSDT"])  # config base sigue en BTCUSDT

    response = client.post(
        "/paper-trading/sessions",
        json=_session_payload(strategy["id"], symbol="ETHUSDT"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "ETHUSDT"
    assert body["config"]["symbol"] == "ETHUSDT"


def test_create_session_does_not_persist_when_first_tick_fails(monkeypatch):
    def _raise(db, session):
        raise RuntimeError("símbolo inválido")

    monkeypatch.setattr("tradingos.api.routers.paper_trading.run_tick_for_session", _raise)
    token = _register_and_get_token("firsttickfail@example.com")
    strategy = _create_strategy(token)

    response = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert response.status_code == 400

    db = SessionLocal()
    try:
        assert db.query(PaperTradingSession).count() == 0
    finally:
        db.close()


def test_create_session_rejects_when_strategy_is_paused(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("pausada@example.com")
    strategy = _create_strategy(token)
    pause = client.patch(f"/strategies/{strategy['id']}", json={"status": "paused"}, headers=_auth_headers(token))
    assert pause.status_code == 200

    response = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert response.status_code == 400
    assert "pausada" in response.json()["detail"]


def test_create_session_rejects_duplicate_active_session_same_symbol_and_timeframe(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("duplicada@example.com")
    strategy = _create_strategy(token)
    first = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert first.status_code == 200

    second = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert second.status_code == 400
    assert "activa" in second.json()["detail"]


def test_create_session_allows_multiple_concurrent_active_sessions(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("concurrent@example.com")
    strategy = _create_strategy(token, symbols=["BTCUSDT", "ETHUSDT"])

    first = client.post(
        "/paper-trading/sessions", json=_session_payload(strategy["id"], symbol="BTCUSDT"), headers=_auth_headers(token)
    )
    second = client.post(
        "/paper-trading/sessions", json=_session_payload(strategy["id"], symbol="ETHUSDT"), headers=_auth_headers(token)
    )
    assert first.status_code == 200
    assert second.status_code == 200

    listed = client.get("/paper-trading/sessions", headers=_auth_headers(token))
    statuses = {s["id"]: s["status"] for s in listed.json()}
    assert statuses == {first.json()["id"]: "active", second.json()["id"]: "active"}


def test_stop_session_allows_creating_a_new_one(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("restart@example.com")
    strategy = _create_strategy(token)

    first = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    session_id = first.json()["id"]

    stop_response = client.post(f"/paper-trading/sessions/{session_id}/stop", headers=_auth_headers(token))
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    second = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert second.status_code == 200


def test_list_sessions_only_returns_own_user(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner@example.com")
    token_b = _register_and_get_token("other@example.com")
    strategy_a = _create_strategy(token_a)

    client.post("/paper-trading/sessions", json=_session_payload(strategy_a["id"]), headers=_auth_headers(token_a))

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
    strategy = _create_strategy(token)

    created = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
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
    strategy = _create_strategy(token)

    created = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token))
    assert created.status_code == 200
    assert created.json()["config"]["symbol"] == "BTCUSDT"

    listed = client.get("/paper-trading/sessions", headers=_auth_headers(token))
    assert listed.json()[0]["config"]["symbol"] == "BTCUSDT"


def test_session_detail_for_other_users_session_returns_404(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner2@example.com")
    token_b = _register_and_get_token("other2@example.com")
    strategy = _create_strategy(token_a)

    created = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token_a))
    session_id = created.json()["id"]

    response = client.get(f"/paper-trading/sessions/{session_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_stop_session_for_other_users_session_returns_404(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner3@example.com")
    token_b = _register_and_get_token("other3@example.com")
    strategy = _create_strategy(token_a)

    created = client.post("/paper-trading/sessions", json=_session_payload(strategy["id"]), headers=_auth_headers(token_a))
    session_id = created.json()["id"]

    response = client.post(f"/paper-trading/sessions/{session_id}/stop", headers=_auth_headers(token_b))
    assert response.status_code == 404
