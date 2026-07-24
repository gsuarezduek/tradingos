from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import Strategy, StrategyConfig, get_strategy, list_strategies
from tradingos.data.loader import load_ohlcv
from tradingos.optimize.grid import ParameterGrid, combination_count
from tradingos.optimize.optimizer import OptimizationResult, run_grid_search
from tradingos.strategies.ma_crossover import default_config, example_grid

# No se puede derivar de __file__: bajo una instalación no editable (como en la imagen
# Docker) el paquete vive en site-packages, desconectado del checkout del repo. Se
# resuelve contra el directorio de trabajo (la raíz del repo, tanto localmente como en
# el WORKDIR del contenedor), con override explícito disponible para otros layouts.
DATA_DIR = Path(os.environ.get("TRADINGOS_DATA_DIR", "data/historical")).resolve()
DEMO_DATASET = "BTCUSDT_1h.parquet"
MAX_GRID_COMBINATIONS = 200

app = FastAPI(title="Trading OS API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/strategies")
def strategies() -> list[str]:
    return list_strategies()


def _resolve_dataset(dataset: str) -> Path:
    dataset_path = (DATA_DIR / dataset).resolve()
    if not dataset_path.is_relative_to(DATA_DIR) or not dataset_path.is_file():
        raise HTTPException(status_code=404, detail="dataset no encontrado")
    return dataset_path


def _resolve_strategy(name: str) -> type[Strategy]:
    try:
        return get_strategy(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _run_backtest(strategy_cls: type[Strategy], config: StrategyConfig, dataset_path: Path, initial_equity: float) -> dict:
    data = load_ohlcv(dataset_path)
    strategy = strategy_cls(config)
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=initial_equity)
    result = engine.run(data)
    weekly_equity = result.equity_curve.resample("W").last().dropna()
    return {
        "num_trades": len(result.trades),
        "metrics": result.metrics,
        "equity_curve": [{"timestamp": ts.isoformat(), "equity": float(value)} for ts, value in weekly_equity.items()],
    }


class BacktestRequest(BaseModel):
    strategy: str
    dataset: str  # nombre de archivo dentro de data/historical, ej "BTCUSDT_1h.parquet"
    config: StrategyConfig
    initial_equity: float = 10_000.0


@app.post("/backtests")
def run_backtest(request: BacktestRequest) -> dict:
    dataset_path = _resolve_dataset(request.dataset)
    strategy_cls = _resolve_strategy(request.strategy)
    return _run_backtest(strategy_cls, request.config, dataset_path, request.initial_equity)


@app.get("/backtests/demo")
def demo_backtest() -> dict:
    """Backtest fijo (ma_crossover sobre BTCUSDT 1h) para alimentar el dashboard con un
    resultado real sin que el cliente tenga que mandar un StrategyConfig completo."""
    dataset_path = DATA_DIR / DEMO_DATASET
    strategy_cls = get_strategy("ma_crossover")
    return _run_backtest(strategy_cls, default_config(), dataset_path, initial_equity=10_000.0)


def _serialize_optimization(results: list[OptimizationResult], grid: ParameterGrid, top_n: int) -> dict:
    return {
        "total_combinations": combination_count(grid),
        "results": [{"config": r.config.model_dump(), "metrics": r.metrics} for r in results[:top_n]],
    }


class OptimizeRequest(BaseModel):
    strategy: str
    dataset: str
    config: StrategyConfig  # config base sobre la que se aplican los overrides de `grid`
    grid: ParameterGrid
    initial_equity: float = 10_000.0
    rank_by: str = "profit_factor"
    top_n: int = 20


@app.post("/optimize")
def optimize(request: OptimizeRequest) -> dict:
    if not request.grid:
        raise HTTPException(status_code=400, detail="grid no puede estar vacío")

    total = combination_count(request.grid)
    if total > MAX_GRID_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"la grilla tiene {total} combinaciones, el máximo permitido es {MAX_GRID_COMBINATIONS}",
        )

    dataset_path = _resolve_dataset(request.dataset)
    strategy_cls = _resolve_strategy(request.strategy)

    data = load_ohlcv(dataset_path)
    results = run_grid_search(strategy_cls, request.config, request.grid, data, request.initial_equity, request.rank_by)
    return _serialize_optimization(results, request.grid, request.top_n)


@app.get("/optimize/demo")
def optimize_demo() -> dict:
    """Grid search fijo (example_grid() de ma_crossover sobre BTCUSDT 1h), mismo
    espíritu que /backtests/demo: no requiere que el cliente arme el request completo."""
    dataset_path = DATA_DIR / DEMO_DATASET
    strategy_cls = get_strategy("ma_crossover")
    grid = example_grid()

    data = load_ohlcv(dataset_path)
    results = run_grid_search(strategy_cls, default_config(), grid, data, initial_equity=10_000.0)
    return _serialize_optimization(results, grid, top_n=10)
