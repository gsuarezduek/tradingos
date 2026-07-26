from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.api.routers import auth as auth_router
from tradingos.api.routers import brokers as brokers_router
from tradingos.api.routers import live_trading as live_trading_router
from tradingos.api.routers import paper_trading as paper_trading_router
from tradingos.api.routers import strategies as strategies_router
from tradingos.backtest.service import (
    DATA_DIR,
    resolve_dataset,
    resolve_strategy,
    run_backtest_result,
    run_backtest_summary,
)
from tradingos.core.strategy import StrategyConfig, get_strategy
from tradingos.data.loader import load_ohlcv
from tradingos.db.migrate import run_migrations
from tradingos.montecarlo.simulator import MonteCarloResult, run_monte_carlo
from tradingos.optimize.grid import ParameterGrid, combination_count
from tradingos.optimize.optimizer import OptimizationResult, run_grid_search
from tradingos.strategies.ma_crossover import default_config

DEMO_DATASET = "BTCUSDT_1h.parquet"

# Medido en producción: ~8s por backtest completo sobre BTCUSDT_1h (~5x más lento que
# en desarrollo local). El servidor corre un solo proceso/worker, así que un request
# que tarda mucho no solo hace esperar a quien lo pidió: bloquea al resto del tráfico
# mientras corre (lo vimos en vivo: /optimize/demo con 27 combinaciones dejó
# /backtests/demo sin responder varios minutos). El tope existe para proteger la
# disponibilidad del servicio, no solo para evitar un timeout del lado del cliente.
MAX_GRID_COMBINATIONS = 12

# Grilla deliberadamente chica para el endpoint público /optimize/demo — a ~8s por
# combinación, 2 ya son ~16s. example_grid() (más grande, pensada para explorar desde
# el script CLI, que no tiene un proxy HTTP con timeout de por medio) no es apta acá.
_DEMO_GRID: ParameterGrid = {
    "indicators.ema_fast.period": [8, 12],
}

# A diferencia del grid search, el Monte Carlo resamplea los P&L de los trades ya
# calculados por un único backtest (numpy puro sobre una lista corta de números): no
# vuelve a correr el motor bar-a-bar por simulación, así que el límite acá es solo
# para no devolver una respuesta desproporcionada, no por riesgo de bloquear el server.
MAX_MONTE_CARLO_SIMULATIONS = 5000


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Trading OS API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(brokers_router.router)
app.include_router(live_trading_router.router)
app.include_router(paper_trading_router.router)
app.include_router(strategies_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class BacktestRequest(BaseModel):
    strategy: str
    dataset: str  # nombre de archivo dentro de data/historical, ej "BTCUSDT_1h.parquet"
    config: StrategyConfig
    initial_equity: float = 10_000.0


@app.post("/backtests")
def run_backtest(request: BacktestRequest) -> dict:
    dataset_path = resolve_dataset(request.dataset, DATA_DIR)
    strategy_cls = resolve_strategy(request.strategy)
    return run_backtest_summary(strategy_cls, request.config, dataset_path, request.initial_equity)


@app.get("/backtests/demo")
def demo_backtest() -> dict:
    """Backtest fijo (ma_crossover sobre BTCUSDT 1h) para alimentar el dashboard con un
    resultado real sin que el cliente tenga que mandar un StrategyConfig completo."""
    dataset_path = DATA_DIR / DEMO_DATASET
    strategy_cls = get_strategy("ma_crossover")
    return run_backtest_summary(strategy_cls, default_config(), dataset_path, initial_equity=10_000.0)


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

    dataset_path = resolve_dataset(request.dataset, DATA_DIR)
    strategy_cls = resolve_strategy(request.strategy)

    data = load_ohlcv(dataset_path)
    results = run_grid_search(strategy_cls, request.config, request.grid, data, request.initial_equity, request.rank_by)
    return _serialize_optimization(results, request.grid, request.top_n)


@app.get("/optimize/demo")
def optimize_demo() -> dict:
    """Grid search fijo y chico (ma_crossover sobre BTCUSDT 1h), mismo espíritu que
    /backtests/demo: no requiere que el cliente arme el request completo, y usa
    _DEMO_GRID (no example_grid()) para que la respuesta sea rápida en cualquier
    entorno."""
    dataset_path = DATA_DIR / DEMO_DATASET
    strategy_cls = get_strategy("ma_crossover")

    data = load_ohlcv(dataset_path)
    results = run_grid_search(strategy_cls, default_config(), _DEMO_GRID, data, initial_equity=10_000.0)
    return _serialize_optimization(results, _DEMO_GRID, top_n=10)


def _serialize_monte_carlo(result: MonteCarloResult) -> dict:
    return {
        "num_simulations": result.num_simulations,
        "initial_equity": result.initial_equity,
        "original_metrics": result.original_metrics,
        "final_equity_percentiles": result.final_equity_percentiles,
        "max_drawdown_percentiles": result.max_drawdown_percentiles,
        "probability_of_profit": result.probability_of_profit,
    }


class MonteCarloRequest(BaseModel):
    strategy: str
    dataset: str
    config: StrategyConfig
    initial_equity: float = 10_000.0
    num_simulations: int = 1000


@app.post("/montecarlo")
def montecarlo(request: MonteCarloRequest) -> dict:
    if not 0 < request.num_simulations <= MAX_MONTE_CARLO_SIMULATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"num_simulations debe estar entre 1 y {MAX_MONTE_CARLO_SIMULATIONS}",
        )

    dataset_path = resolve_dataset(request.dataset, DATA_DIR)
    strategy_cls = resolve_strategy(request.strategy)

    backtest_result = run_backtest_result(strategy_cls, request.config, dataset_path, request.initial_equity)
    mc_result = run_monte_carlo(
        backtest_result.trades,
        request.initial_equity,
        backtest_result.metrics,
        num_simulations=request.num_simulations,
    )
    return _serialize_monte_carlo(mc_result)


@app.get("/montecarlo/demo")
def montecarlo_demo() -> dict:
    """Monte Carlo fijo (ma_crossover sobre BTCUSDT 1h), mismo espíritu que
    /backtests/demo y /optimize/demo. A diferencia de /optimize/demo, acá el costo
    dominante es el único backtest previo: resamplear sus trades con numpy es barato
    aunque num_simulations sea alto."""
    dataset_path = DATA_DIR / DEMO_DATASET
    strategy_cls = get_strategy("ma_crossover")

    backtest_result = run_backtest_result(strategy_cls, default_config(), dataset_path, initial_equity=10_000.0)
    mc_result = run_monte_carlo(backtest_result.trades, 10_000.0, backtest_result.metrics, num_simulations=1000)
    return _serialize_monte_carlo(mc_result)
