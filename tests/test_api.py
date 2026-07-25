from fastapi.testclient import TestClient

from tradingos.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_strategies_includes_ma_crossover():
    response = client.get("/strategies/catalog")
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


def test_demo_backtest_includes_equity_curve():
    response = client.get("/backtests/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["num_trades"] > 0
    assert "metrics" in body
    assert len(body["equity_curve"]) > 0
    first_point = body["equity_curve"][0]
    assert "timestamp" in first_point
    assert "equity" in first_point


def test_optimize_demo_returns_ranked_results():
    response = client.get("/optimize/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["total_combinations"] == 2  # ver _DEMO_GRID en api/main.py
    assert len(body["results"]) == 2
    scores = [r["metrics"]["profit_factor"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_optimize_returns_expected_combination_count():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "BTCUSDT_1h.parquet",
        "config": {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "stop_loss_pct": 0.02,
            "indicators": {
                "ema_fast": {"period": 12},
                "ema_slow": {"period": 26},
                "atr": {"period": 14, "min_value_pct": 0.001},
            },
        },
        "grid": {"stop_loss_pct": [0.01, 0.02], "take_profit_pct": [0.03, 0.04]},
        "top_n": 20,
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["total_combinations"] == 4
    assert len(body["results"]) == 4


def test_optimize_rejects_oversized_grid():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "BTCUSDT_1h.parquet",
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.02},
        "grid": {"stop_loss_pct": [0.01 * i for i in range(1, 21)], "take_profit_pct": [0.01 * i for i in range(1, 21)]},
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 400


def test_optimize_rejects_empty_grid():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "BTCUSDT_1h.parquet",
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.02},
        "grid": {},
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 400


def test_montecarlo_demo_returns_ordered_percentiles():
    response = client.get("/montecarlo/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["num_simulations"] == 1000
    equity_values = [body["final_equity_percentiles"][f"p{p}"] for p in (5, 25, 50, 75, 95)]
    assert equity_values == sorted(equity_values)
    assert 0.0 <= body["probability_of_profit"] <= 1.0


def test_montecarlo_returns_requested_num_simulations():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "BTCUSDT_1h.parquet",
        "config": {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "stop_loss_pct": 0.02,
            "indicators": {
                "ema_fast": {"period": 12},
                "ema_slow": {"period": 26},
                "atr": {"period": 14, "min_value_pct": 0.001},
            },
        },
        "num_simulations": 50,
    }
    response = client.post("/montecarlo", json=payload)
    assert response.status_code == 200
    assert response.json()["num_simulations"] == 50


def test_montecarlo_rejects_oversized_num_simulations():
    payload = {
        "strategy": "ma_crossover",
        "dataset": "BTCUSDT_1h.parquet",
        "config": {"symbol": "BTCUSDT", "timeframe": "1h", "stop_loss_pct": 0.02},
        "num_simulations": 10_000,
    }
    response = client.post("/montecarlo", json=payload)
    assert response.status_code == 400
