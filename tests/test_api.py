from fastapi.testclient import TestClient

from tradingos.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_strategies_includes_ma_crossover():
    response = client.get("/strategies")
    assert response.status_code == 200
    assert "ma_crossover" in response.json()


def test_backtest_rejects_unknown_dataset():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "no_existe.parquet",
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.02},
    }
    response = client.post("/backtests", json=payload)
    assert response.status_code == 404


def test_backtest_rejects_path_traversal():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "../../pyproject.toml",
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.02},
    }
    response = client.post("/backtests", json=payload)
    assert response.status_code == 404


def test_backtest_rejects_unknown_strategy():
    payload = {
        "strategy": "no_existe",
        "dataset": "no_existe.parquet",
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.02},
    }
    response = client.post("/backtests", json=payload)
    assert response.status_code == 404
