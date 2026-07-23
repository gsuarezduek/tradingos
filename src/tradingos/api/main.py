from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import StrategyConfig, get_strategy, list_strategies
from tradingos.data.loader import load_ohlcv

DATA_DIR = (Path(__file__).resolve().parents[3] / "data" / "historical").resolve()

app = FastAPI(title="Trading OS API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/strategies")
def strategies() -> list[str]:
    return list_strategies()


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

    data = load_ohlcv(dataset_path)
    strategy = strategy_cls(request.config)
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=request.initial_equity)
    result = engine.run(data)
    return {"num_trades": len(result.trades), "metrics": result.metrics}
