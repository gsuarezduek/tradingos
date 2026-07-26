from fastapi.testclient import TestClient

from tradingos.api.main import app
from tradingos.db.models import LiveTrade, LiveTradingSession, User
from tradingos.db.session import SessionLocal
from tradingos.strategies.ma_crossover import default_config

client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_strategy(token: str, **overrides) -> dict:
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


def _create_connection(token: str, monkeypatch, *, trading_enabled: bool = True) -> dict:
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    response = client.post(
        "/brokers/binance/connections",
        json={"api_key": "k", "api_secret": "s", "label": "cuenta"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    connection = response.json()
    if trading_enabled:
        toggle = client.patch(
            f"/brokers/binance/connections/{connection['id']}",
            json={"trading_enabled": True},
            headers=_auth_headers(token),
        )
        assert toggle.status_code == 200
    return connection


def _session_payload(strategy_id: int, connection_id: int, *, symbol: str = "BTCUSDT", timeframe: str = "1h") -> dict:
    return {"strategy_id": strategy_id, "broker_connection_id": connection_id, "symbol": symbol, "timeframe": timeframe}


def _mock_tick_ok(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.live_trading.run_tick_for_session", lambda db, session: None)


def test_create_session_requires_auth():
    response = client.post("/live-trading/sessions", json=_session_payload(1, 1))
    assert response.status_code == 401


def test_create_session_rejects_unsupported_timeframe(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tf@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"], timeframe="2h"),  # no está en SUPPORTED_TIMEFRAMES
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_create_session_rejects_timeframe_faster_than_cron(monkeypatch):
    # El cron de trading en vivo corre cada 15m; algo más rápido (5m acá) se podría
    # perder en silencio entre ticks — ver _MIN_LIVE_TRADING_INTERVAL_MS.
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tooFast@example.com")
    strategy = _create_strategy(token, timeframes=["1h", "5m"])
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"], timeframe="5m"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400
    assert "cron" in response.json()["detail"]


def test_create_session_supports_timeframes_other_than_1h(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tf4h@example.com")
    strategy = _create_strategy(token, timeframes=["1h", "4h"])
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"], timeframe="4h"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["timeframe"] == "4h"


def test_limits_reports_eligible_timeframes_matching_the_cron_floor(monkeypatch):
    token = _register_and_get_token("limits@example.com")

    response = client.get("/live-trading/limits", headers=_auth_headers(token))

    assert response.status_code == 200
    eligible = response.json()["eligible_timeframes"]
    assert "5m" not in eligible  # más rápida que el cron
    assert eligible == ["15m", "30m", "1h", "4h", "1d", "1w"]  # ordenadas de más rápida a más lenta


def test_risk_settings_round_trip(monkeypatch):
    token = _register_and_get_token("risksettings@example.com")

    initial = client.get("/live-trading/risk-settings", headers=_auth_headers(token))
    assert initial.status_code == 200
    assert initial.json() == {"daily_loss_limit_usdt": None, "weekly_loss_limit_usdt": None}

    updated = client.patch(
        "/live-trading/risk-settings",
        json={"daily_loss_limit_usdt": 100.0, "weekly_loss_limit_usdt": 300.0},
        headers=_auth_headers(token),
    )
    assert updated.status_code == 200
    assert updated.json() == {"daily_loss_limit_usdt": 100.0, "weekly_loss_limit_usdt": 300.0}

    disabled = client.patch(
        "/live-trading/risk-settings",
        json={"daily_loss_limit_usdt": None, "weekly_loss_limit_usdt": 300.0},
        headers=_auth_headers(token),
    )
    assert disabled.status_code == 200
    assert disabled.json() == {"daily_loss_limit_usdt": None, "weekly_loss_limit_usdt": 300.0}


def test_risk_settings_rejects_non_positive_limit(monkeypatch):
    token = _register_and_get_token("risksettingsneg@example.com")

    response = client.patch(
        "/live-trading/risk-settings",
        json={"daily_loss_limit_usdt": -10.0, "weekly_loss_limit_usdt": None},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_session_rejected_when_daily_loss_limit_is_breached(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("breached@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)

    set_limit = client.patch(
        "/live-trading/risk-settings",
        json={"daily_loss_limit_usdt": 50.0, "weekly_loss_limit_usdt": None},
        headers=_auth_headers(token),
    )
    assert set_limit.status_code == 200

    db = SessionLocal()
    try:
        from datetime import datetime, timedelta, timezone

        user = db.query(User).filter(User.email == "breached@example.com").first()
        session = LiveTradingSession(
            user_id=user.id,
            strategy_id=strategy["id"],
            broker_connection_id=connection["id"],
            exchange="binance",
            strategy="ma_crossover",
            symbol="BTCUSDT",
            timeframe="1h",
            config=default_config(symbol="BTCUSDT").model_dump(),
            status="stopped",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        db.add(
            LiveTrade(
                session_id=session.id,
                side="long",
                entry_timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
                exit_timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
                entry_price=100.0,
                exit_price=40.0,
                quantity=1.0,
                pnl=-60.0,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"]),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400
    assert "límite de pérdida diaria" in response.json()["detail"]


def test_create_session_rejects_unknown_strategy(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("unknownstrat@example.com")
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions", json=_session_payload(999_999, connection["id"]), headers=_auth_headers(token)
    )
    assert response.status_code == 404


def test_create_session_rejects_unknown_connection(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("unknownconn@example.com")
    strategy = _create_strategy(token)

    response = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], 999_999), headers=_auth_headers(token)
    )
    assert response.status_code == 404


def test_create_session_rejects_when_trading_not_enabled(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("notenabled@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch, trading_enabled=False)

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"]),
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_create_session_rejects_symbol_not_declared_by_strategy(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("symbolnotdeclared@example.com")
    strategy = _create_strategy(token)  # symbols=["BTCUSDT"]
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"], symbol="SOLUSDT"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400
    assert "SOLUSDT" in response.json()["detail"]


def test_create_session_rejects_when_strategy_is_paused(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("pausada@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)
    pause = client.patch(f"/strategies/{strategy['id']}", json={"status": "paused"}, headers=_auth_headers(token))
    assert pause.status_code == 200

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"]),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400
    assert "pausada" in response.json()["detail"]


def test_create_session_rejects_duplicate_active_session_same_strategy_symbol_and_connection(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("duplicada@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)
    first = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"]),
        headers=_auth_headers(token),
    )
    assert first.status_code == 200

    second = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"]),
        headers=_auth_headers(token),
    )
    assert second.status_code == 400
    assert "activa" in second.json()["detail"]


def test_create_session_rejects_when_max_active_sessions_reached(monkeypatch):
    from tradingos.api.routers.live_trading import MAX_ACTIVE_LIVE_TRADING_SESSIONS

    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tope@example.com")
    symbols = ["BTCUSDT"] + [f"SYM{i}USDT" for i in range(MAX_ACTIVE_LIVE_TRADING_SESSIONS)]
    strategy = _create_strategy(token, symbols=symbols)
    connection = _create_connection(token, monkeypatch)

    for symbol in symbols[:MAX_ACTIVE_LIVE_TRADING_SESSIONS]:
        response = client.post(
            "/live-trading/sessions",
            json=_session_payload(strategy["id"], connection["id"], symbol=symbol),
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.json()

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"], symbol=symbols[-1]),
        headers=_auth_headers(token),
    )
    assert response.status_code == 400
    assert "máximo" in response.json()["detail"]


def test_create_session_allows_new_session_after_stopping_one_at_the_cap(monkeypatch):
    from tradingos.api.routers.live_trading import MAX_ACTIVE_LIVE_TRADING_SESSIONS

    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("tope-liberado@example.com")
    symbols = ["BTCUSDT"] + [f"SYM{i}USDT" for i in range(MAX_ACTIVE_LIVE_TRADING_SESSIONS)]
    strategy = _create_strategy(token, symbols=symbols)
    connection = _create_connection(token, monkeypatch)

    created_ids = []
    for symbol in symbols[:MAX_ACTIVE_LIVE_TRADING_SESSIONS]:
        response = client.post(
            "/live-trading/sessions",
            json=_session_payload(strategy["id"], connection["id"], symbol=symbol),
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.json()
        created_ids.append(response.json()["id"])

    stop_response = client.post(f"/live-trading/sessions/{created_ids[0]}/stop", headers=_auth_headers(token))
    assert stop_response.status_code == 200

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection["id"], symbol=symbols[-1]),
        headers=_auth_headers(token),
    )
    assert response.status_code == 200


def test_create_session_rejects_another_users_connection(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner-conn@example.com")
    token_b = _register_and_get_token("other-conn@example.com")
    strategy = _create_strategy(token_a)
    connection_b = _create_connection(token_b, monkeypatch)

    response = client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy["id"], connection_b["id"]),
        headers=_auth_headers(token_a),
    )
    assert response.status_code == 404


def test_create_session_succeeds_and_ticks_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "tradingos.api.routers.live_trading.run_tick_for_session",
        lambda db, session: calls.append(session.id),
    )
    token = _register_and_get_token("ok@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], connection["id"]), headers=_auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["strategy_id"] == strategy["id"]
    assert body["strategy_name"] == strategy["name"]
    assert body["broker_connection_id"] == connection["id"]
    assert body["exchange"] == "binance"
    assert calls == [body["id"]]


def test_create_session_does_not_persist_when_first_tick_fails(monkeypatch):
    def _raise(db, session):
        raise RuntimeError("símbolo inválido")

    monkeypatch.setattr("tradingos.api.routers.live_trading.run_tick_for_session", _raise)
    token = _register_and_get_token("firsttickfail@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)

    response = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], connection["id"]), headers=_auth_headers(token)
    )
    assert response.status_code == 400

    db = SessionLocal()
    try:
        assert db.query(LiveTradingSession).count() == 0
    finally:
        db.close()


def test_list_sessions_only_returns_own_user(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner@example.com")
    token_b = _register_and_get_token("other@example.com")
    strategy_a = _create_strategy(token_a)
    connection_a = _create_connection(token_a, monkeypatch)

    client.post(
        "/live-trading/sessions",
        json=_session_payload(strategy_a["id"], connection_a["id"]),
        headers=_auth_headers(token_a),
    )

    response_a = client.get("/live-trading/sessions", headers=_auth_headers(token_a))
    response_b = client.get("/live-trading/sessions", headers=_auth_headers(token_b))

    assert len(response_a.json()) == 1
    assert response_b.json() == []


def test_session_detail_includes_trades_and_orders(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token = _register_and_get_token("detail@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)

    created = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], connection["id"]), headers=_auth_headers(token)
    )
    session_id = created.json()["id"]

    response = client.get(f"/live-trading/sessions/{session_id}", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert body["orders"] == []
    assert body["current_position"] is None


def test_stop_session_does_not_clear_current_position(monkeypatch):
    fake_position = {
        "side": "long",
        "entry_price": 100.0,
        "quantity": 1.0,
        "stop_loss": 98.0,
        "take_profit": 104.0,
        "entry_timestamp": "2024-01-01T00:00:00+00:00",
        "opened_at": "2024-01-01T00:00:00+00:00",
    }

    def _fake_tick(db, session):
        session.current_position = fake_position
        db.commit()

    monkeypatch.setattr("tradingos.api.routers.live_trading.run_tick_for_session", _fake_tick)
    token = _register_and_get_token("stopwithposition@example.com")
    strategy = _create_strategy(token)
    connection = _create_connection(token, monkeypatch)

    created = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], connection["id"]), headers=_auth_headers(token)
    )
    session_id = created.json()["id"]
    assert created.json()["current_position"] == fake_position

    stop_response = client.post(f"/live-trading/sessions/{session_id}/stop", headers=_auth_headers(token))
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"
    assert stop_response.json()["current_position"] == fake_position  # no se toca, es plata real


def test_session_detail_for_other_users_session_returns_404(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner2@example.com")
    token_b = _register_and_get_token("other2@example.com")
    strategy = _create_strategy(token_a)
    connection = _create_connection(token_a, monkeypatch)

    created = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], connection["id"]), headers=_auth_headers(token_a)
    )
    session_id = created.json()["id"]

    response = client.get(f"/live-trading/sessions/{session_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_stop_session_for_other_users_session_returns_404(monkeypatch):
    _mock_tick_ok(monkeypatch)
    token_a = _register_and_get_token("owner3@example.com")
    token_b = _register_and_get_token("other3@example.com")
    strategy = _create_strategy(token_a)
    connection = _create_connection(token_a, monkeypatch)

    created = client.post(
        "/live-trading/sessions", json=_session_payload(strategy["id"], connection["id"]), headers=_auth_headers(token_a)
    )
    session_id = created.json()["id"]

    response = client.post(f"/live-trading/sessions/{session_id}/stop", headers=_auth_headers(token_b))
    assert response.status_code == 404
