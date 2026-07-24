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
from tradingos.strategies.ma_crossover import default_config

# No se puede derivar de __file__: bajo una instalación no editable (como en la imagen
# Docker) el paquete vive en site-packages, desconectado del checkout del repo. Se
# resuelve contra el directorio de trabajo (la raíz del repo, tanto localmente como en
# el WORKDIR del contenedor), con override explícito disponible para otros layouts.
DATA_DIR = Path(os.environ.get("TRADINGOS_DATA_DIR", "data/historical")).resolve()
DEMO_DATASET = "BTCUSDT_1h.parquet"

app = FastAPI(title="Trading OS API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/strategies")
def strategies() -> list[str]:
    return list_strategies()


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
    dataset_path = (DATA_DIR / request.dataset).resolve()
    if not dataset_path.is_relative_to(DATA_DIR) or not dataset_path.is_file():
        raise HTTPException(status_code=404, detail="dataset no encontrado")

    try:
        strategy_cls = get_strategy(request.strategy)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _run_backtest(strategy_cls, request.config, dataset_path, request.initial_equity)


@app.get("/backtests/demo")
def demo_backtest() -> dict:
    """Backtest fijo (ma_crossover sobre BTCUSDT 1h) para alimentar el dashboard con un
    resultado real sin que el cliente tenga que mandar un StrategyConfig completo."""
    dataset_path = DATA_DIR / DEMO_DATASET
    strategy_cls = get_strategy("ma_crossover")
    return _run_backtest(strategy_cls, default_config(), dataset_path, initial_equity=10_000.0)
