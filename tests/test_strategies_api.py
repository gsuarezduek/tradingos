from fastapi.testclient import TestClient

from tradingos.api.main import app
from tradingos.db.models import SavedStrategy
from tradingos.db.session import SessionLocal
from tradingos.strategies.ma_crossover import default_config

client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_payload(**overrides) -> dict:
    payload = {
        "name": "Mi EMA Crossover",
        "strategy_type": "ma_crossover",
        "category": "swing",
        "symbols": ["BTCUSDT"],
        "timeframes": ["1h"],
        "config": default_config(symbol="BTCUSDT", timeframe="1h").model_dump(),
        "notes": "estrategia de prueba",
        "initial_equity": 10_000.0,
    }
    payload.update(overrides)
    return payload


def test_create_strategy_requires_auth():
    response = client.post("/strategies", json=_create_payload())
    assert response.status_code == 401


def test_create_strategy_runs_first_backtest_and_persists():
    token = _register_and_get_token("crea@example.com")
    response = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Mi EMA Crossover"
    assert data["status"] == "active"
    assert len(data["backtest_runs"]) == 1
    first_run = data["backtest_runs"][0]
    assert first_run["symbol"] == "BTCUSDT"
    assert first_run["timeframe"] == "1h"
    assert first_run["num_trades"] > 0
    # el resumen embebido en el detalle no trae equity_curve/trades pesados
    assert "equity_curve" not in first_run
    assert "trades" not in first_run


def test_create_strategy_rejects_symbol_without_dataset():
    token = _register_and_get_token("sindataset@example.com")
    payload = _create_payload(
        symbols=["ETHUSDT"],
        timeframes=["1h"],
        config=default_config(symbol="ETHUSDT", timeframe="1h").model_dump(),
    )
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 400
    assert "ETHUSDT" in response.json()["detail"]

    from tradingos.db.session import SessionLocal

    db = SessionLocal()
    try:
        assert db.query(SavedStrategy).count() == 0
    finally:
        db.close()


def test_create_strategy_rejects_invalid_category():
    token = _register_and_get_token("categoria@example.com")
    response = client.post(
        "/strategies", json=_create_payload(category="hodl"), headers=_auth_headers(token)
    )
    assert response.status_code == 422


def test_create_strategy_accepts_new_extended_timeframes():
    token = _register_and_get_token("timeframes-nuevas@example.com")
    # "1w" es solo metadata declarativa (sin dataset todavía); el primer backtest corre
    # igual en "1h" porque config.timeframe sigue siendo esa.
    payload = _create_payload(timeframes=["1h", "1w"])
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["timeframes"] == ["1h", "1w"]


def test_create_strategy_rejects_unsupported_timeframe():
    token = _register_and_get_token("timeframe-invalida@example.com")
    payload = _create_payload(timeframes=["2h"])
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 400
    assert "2h" in response.json()["detail"]


def test_list_and_detail_isolated_by_user():
    token_a = _register_and_get_token("usera@example.com")
    token_b = _register_and_get_token("userb@example.com")

    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token_a))
    strategy_id = created.json()["id"]

    list_a = client.get("/strategies", headers=_auth_headers(token_a))
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["latest_run"]["symbol"] == "BTCUSDT"

    list_b = client.get("/strategies", headers=_auth_headers(token_b))
    assert list_b.json() == []

    detail_b = client.get(f"/strategies/{strategy_id}", headers=_auth_headers(token_b))
    assert detail_b.status_code == 404

    patch_b = client.patch(f"/strategies/{strategy_id}", json={"status": "paused"}, headers=_auth_headers(token_b))
    assert patch_b.status_code == 404


def _create_broker_connection(token: str, monkeypatch) -> dict:
    monkeypatch.setattr("tradingos.api.routers.brokers.get_spot_balances", lambda api_key, api_secret: [])
    response = client.post(
        "/brokers/binance/connections",
        json={"api_key": "k", "api_secret": "s", "label": "cuenta"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    connection = response.json()
    toggle = client.patch(
        f"/brokers/binance/connections/{connection['id']}",
        json={"trading_enabled": True},
        headers=_auth_headers(token),
    )
    assert toggle.status_code == 200
    return connection


def test_pausing_strategy_stops_active_live_and_paper_trading_sessions(monkeypatch):
    monkeypatch.setattr("tradingos.api.routers.paper_trading.run_tick_for_session", lambda db, session: None)
    monkeypatch.setattr("tradingos.api.routers.live_trading.run_tick_for_session", lambda db, session: None)

    token = _register_and_get_token("pausar-cascada@example.com")
    strategy = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token)).json()
    connection = _create_broker_connection(token, monkeypatch)

    paper = client.post(
        "/paper-trading/sessions",
        json={"strategy_id": strategy["id"], "symbol": "BTCUSDT", "timeframe": "1h", "initial_equity": 10_000.0},
        headers=_auth_headers(token),
    )
    assert paper.status_code == 200
    live = client.post(
        "/live-trading/sessions",
        json={
            "strategy_id": strategy["id"],
            "broker_connection_id": connection["id"],
            "symbol": "BTCUSDT",
            "timeframe": "1h",
        },
        headers=_auth_headers(token),
    )
    assert live.status_code == 200

    pause = client.patch(f"/strategies/{strategy['id']}", json={"status": "paused"}, headers=_auth_headers(token))
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"

    paper_after = client.get("/paper-trading/sessions", headers=_auth_headers(token)).json()
    live_after = client.get("/live-trading/sessions", headers=_auth_headers(token)).json()
    assert next(s for s in paper_after if s["id"] == paper.json()["id"])["status"] == "stopped"
    assert next(s for s in live_after if s["id"] == live.json()["id"])["status"] == "stopped"


def test_pausing_strategy_without_active_sessions_just_changes_status():
    token = _register_and_get_token("pausar-sin-sesiones@example.com")
    strategy = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token)).json()

    response = client.patch(f"/strategies/{strategy['id']}", json={"status": "paused"}, headers=_auth_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "paused"


def test_patch_updates_status_and_notes():
    token = _register_and_get_token("patch@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    response = client.patch(
        f"/strategies/{strategy_id}",
        json={"status": "paused", "notes": "pausada para revisar"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paused"
    assert response.json()["notes"] == "pausada para revisar"


def test_backtests_accumulate_history_without_replacing():
    token = _register_and_get_token("historial@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]
    assert len(created.json()["backtest_runs"]) == 1

    second = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "initial_equity": 5_000.0},
        headers=_auth_headers(token),
    )
    assert second.status_code == 200

    detail = client.get(f"/strategies/{strategy_id}", headers=_auth_headers(token))
    assert len(detail.json()["backtest_runs"]) == 2


def test_run_detail_includes_equity_curve_and_trades():
    token = _register_and_get_token("detalle@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]
    run_id = created.json()["backtest_runs"][0]["id"]

    run_detail = client.get(f"/strategies/{strategy_id}/backtests/{run_id}", headers=_auth_headers(token))

    assert run_detail.status_code == 200
    body = run_detail.json()
    assert len(body["equity_curve"]) > 0
    assert len(body["trades"]) > 0
    assert body["trades"][0]["side"] in ("long", "short")


def test_run_detail_reports_total_pnl_consistent_with_equity_curve():
    token = _register_and_get_token("pnl@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]
    run_id = created.json()["backtest_runs"][0]["id"]

    run_detail = client.get(f"/strategies/{strategy_id}/backtests/{run_id}", headers=_auth_headers(token)).json()

    expected_pnl = run_detail["equity_curve"][-1]["equity"] - run_detail["initial_equity"]
    assert run_detail["total_pnl"] == expected_pnl
    assert created.json()["backtest_runs"][0]["total_pnl"] == expected_pnl


def test_run_backtest_with_date_range_persists_range_and_narrows_data():
    token = _register_and_get_token("rango@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    response = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "initial_equity": 10_000.0,
            "start_date": "2023-01-01",
            "end_date": "2023-06-01",
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["range_start"].startswith("2023-01-01")
    assert body["range_end"].startswith("2023-06-01")
    # Medio año de datos produce menos operaciones que el histórico completo (695 en el
    # fixture de creación, que corre sin rango).
    assert body["num_trades"] < created.json()["backtest_runs"][0]["num_trades"]


def test_run_backtest_rejects_start_after_end():
    token = _register_and_get_token("rango-invalido@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    response = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "start_date": "2023-06-01", "end_date": "2023-01-01"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 400


def test_run_backtest_rejects_range_outside_dataset_coverage():
    token = _register_and_get_token("rango-fuera@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    response = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "start_date": "1990-01-01", "end_date": "1990-06-01"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 400


def test_run_backtest_rejects_symbol_outside_strategy_markets():
    token = _register_and_get_token("fuera@example.com")
    created = client.post("/strategies", json=_create_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    response = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"symbol": "ETHUSDT", "timeframe": "1h", "initial_equity": 10_000.0},
        headers=_auth_headers(token),
    )

    assert response.status_code == 400


def test_catalog_and_datasets_are_public():
    catalog = client.get("/strategies/catalog")
    assert catalog.status_code == 200
    assert "ma_crossover" in catalog.json()

    datasets = client.get("/strategies/datasets")
    assert datasets.status_code == 200
    btc_1h = next(d for d in datasets.json() if d["symbol"] == "BTCUSDT" and d["timeframe"] == "1h")
    assert btc_1h["dataset"] == "BTCUSDT_1h.parquet"
    assert btc_1h["start"] < btc_1h["end"]


def _condition_based_payload(**overrides) -> dict:
    payload = {
        "name": "Estrategia por condiciones",
        "strategy_type": "condition_based",
        "category": "swing",
        "symbols": ["BTCUSDT"],
        "timeframes": ["1h"],
        # Un solo grupo (Y de las dos): forma nueva, lista de grupos.
        "entry_rules": [[{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}]],
        "exit_rules": [[{"category": "ema", "condition_type": "cross_below", "params": {"period_a": 12, "period_b": 26}}]],
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.05, "risk_per_trade": 0.01},
        "notes": "",
        "initial_equity": 10_000.0,
    }
    payload.update(overrides)
    return payload


def test_conditions_catalog_is_public_and_lists_ema_as_available():
    response = client.get("/strategies/conditions/catalog")
    assert response.status_code == 200
    catalog = {c["category"]: c for c in response.json()}
    assert catalog["ema"]["available"] is True
    assert catalog["rsi"]["available"] is True
    assert catalog["volume"]["available"] is True
    assert catalog["price_action"]["available"] is True
    assert catalog["atr"]["available"] is True
    assert catalog["macd"]["available"] is True
    assert catalog["bollinger"]["available"] is True
    assert catalog["adx"]["available"] is True
    assert any(t["type"] == "cross_above" for t in catalog["ema"]["condition_types"])


def test_create_condition_based_strategy_runs_backtest_and_describes_rules():
    token = _register_and_get_token("condiciones@example.com")
    response = client.post("/strategies", json=_condition_based_payload(), headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["entry_rules"] == _condition_based_payload()["entry_rules"]
    assert "EMA12" in body["entry_conditions"] and "EMA26" in body["entry_conditions"]
    assert "EMA12" in body["exit_conditions"] and "EMA26" in body["exit_conditions"]
    assert len(body["backtest_runs"]) == 1


def test_create_condition_based_strategy_requires_entry_rules():
    token = _register_and_get_token("sin-condiciones@example.com")
    response = client.post(
        "/strategies", json=_condition_based_payload(entry_rules=[]), headers=_auth_headers(token)
    )
    assert response.status_code == 422


def test_create_condition_based_strategy_rejects_unavailable_category():
    # Las 8 categorías del catálogo ya están todas disponibles; esto prueba que la
    # validación sigue rechazando una categoría que directamente no existe en el catálogo.
    token = _register_and_get_token("categoria-no-disponible@example.com")
    payload = _condition_based_payload(
        entry_rules=[[{"category": "stochastic", "condition_type": "stochastic_above_80", "params": {}}]]
    )
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 400
    assert "stochastic" in response.json()["detail"]


def test_update_condition_based_strategy_regenerates_description():
    token = _register_and_get_token("editar-condiciones@example.com")
    created = client.post("/strategies", json=_condition_based_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    response = client.patch(
        f"/strategies/{strategy_id}",
        json={"entry_rules": [[{"category": "ema", "condition_type": "price_above", "params": {"period": 50}}]]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["entry_conditions"] == "Precio > EMA50"


def test_create_condition_based_strategy_with_or_groups_describes_and_runs():
    token = _register_and_get_token("grupos-or@example.com")
    payload = _condition_based_payload(
        entry_rules=[
            [{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}],
            [{"category": "rsi", "condition_type": "rsi_below_30", "params": {}}],
        ],
        exit_rules=[[{"category": "ema", "condition_type": "cross_below", "params": {"period_a": 12, "period_b": 26}}]],
    )
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["entry_rules"]) == 2
    assert " O " in body["entry_conditions"]
    assert body["entry_conditions"].count("(") == 2  # cada grupo entre paréntesis
    assert len(body["backtest_runs"]) == 1


def test_condition_based_strategy_rejects_empty_group():
    token = _register_and_get_token("grupo-vacio@example.com")
    payload = _condition_based_payload(entry_rules=[[]])
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    # Un grupo vacío no cuenta como condición: sigue faltando al menos una.
    assert response.status_code == 422


def test_condition_based_strategy_rejects_duplicate_condition_in_same_group():
    token = _register_and_get_token("condicion-repetida@example.com")
    payload = _condition_based_payload(
        entry_rules=[
            [
                {"category": "ema", "condition_type": "price_above", "params": {"period": 20}},
                {"category": "ema", "condition_type": "price_above", "params": {"period": 20}},
            ]
        ]
    )
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 400
    assert "repetida" in response.json()["detail"]


def test_condition_based_strategy_allows_same_condition_across_different_groups():
    token = _register_and_get_token("condicion-en-dos-grupos@example.com")
    payload = _condition_based_payload(
        entry_rules=[
            [{"category": "ema", "condition_type": "price_above", "params": {"period": 20}}],
            [
                {"category": "ema", "condition_type": "price_above", "params": {"period": 20}},
                {"category": "rsi", "condition_type": "rsi_below_50", "params": {}},
            ],
        ]
    )
    response = client.post("/strategies", json=payload, headers=_auth_headers(token))

    assert response.status_code == 200


def test_legacy_flat_entry_rules_are_normalized_and_still_run():
    # Estrategias guardadas antes de que existieran los grupos tienen entry_rules como
    # lista plana de condiciones en la DB (no lista de grupos). El GET debe devolverlas
    # ya normalizadas como un único grupo, y un backtest nuevo debe correr igual que
    # siempre (ver normalize_rule_groups).
    token = _register_and_get_token("legacy-flat@example.com")
    created = client.post("/strategies", json=_condition_based_payload(), headers=_auth_headers(token))
    strategy_id = created.json()["id"]

    db = SessionLocal()
    try:
        strategy = db.query(SavedStrategy).filter(SavedStrategy.id == strategy_id).one()
        strategy.entry_rules = [{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}]
        strategy.exit_rules = [{"category": "ema", "condition_type": "cross_below", "params": {"period_a": 12, "period_b": 26}}]
        db.commit()
    finally:
        db.close()

    detail = client.get(f"/strategies/{strategy_id}", headers=_auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["entry_rules"] == [
        [{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12.0, "period_b": 26.0}}]
    ]

    run = client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "initial_equity": 10_000.0},
        headers=_auth_headers(token),
    )
    assert run.status_code == 200
    assert run.json()["num_trades"] > 0
