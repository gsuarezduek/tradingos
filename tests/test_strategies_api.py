from fastapi.testclient import TestClient

from tradingos.api.main import app
from tradingos.db.models import SavedStrategy
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
        "entry_conditions": "EMA rápida cruza por encima de la lenta con ATR suficiente",
        "exit_conditions": "EMA rápida cruza por debajo de la lenta",
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
    assert {"symbol": "BTCUSDT", "timeframe": "1h", "dataset": "BTCUSDT_1h.parquet"} in datasets.json()
