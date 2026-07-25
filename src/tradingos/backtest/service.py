from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import HTTPException

from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.backtest.result import BacktestResult
from tradingos.core.strategy import Strategy, StrategyConfig, get_strategy
from tradingos.data.loader import load_ohlcv

# No se puede derivar de __file__: bajo una instalación no editable (como en la imagen
# Docker) el paquete vive en site-packages, desconectado del checkout del repo. Se
# resuelve contra el directorio de trabajo (la raíz del repo, tanto localmente como en
# el WORKDIR del contenedor), con override explícito disponible para otros layouts.
DATA_DIR = Path(os.environ.get("TRADINGOS_DATA_DIR", "data/historical")).resolve()

# Convención de nombre de archivo usada en data/historical/, ej "BTCUSDT_1h.parquet".
_DATASET_FILENAME_RE = re.compile(r"^(?P<symbol>[A-Z0-9]+)_(?P<timeframe>[0-9a-zA-Z]+)\.parquet$")


def resolve_dataset(dataset: str, data_dir: Path) -> Path:
    dataset_path = (data_dir / dataset).resolve()
    if not dataset_path.is_relative_to(data_dir) or not dataset_path.is_file():
        raise HTTPException(status_code=404, detail="dataset no encontrado")
    return dataset_path


def resolve_strategy(name: str) -> type[Strategy]:
    try:
        return get_strategy(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def run_backtest_result(
    strategy_cls: type[Strategy], config: StrategyConfig, dataset_path: Path, initial_equity: float
) -> BacktestResult:
    data = load_ohlcv(dataset_path)
    strategy = strategy_cls(config)
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=initial_equity)
    return engine.run(data)


def run_backtest_summary(
    strategy_cls: type[Strategy], config: StrategyConfig, dataset_path: Path, initial_equity: float
) -> dict:
    result = run_backtest_result(strategy_cls, config, dataset_path, initial_equity)
    weekly_equity = result.equity_curve.resample("W").last().dropna()
    return {
        "num_trades": len(result.trades),
        "metrics": result.metrics,
        "equity_curve": [{"timestamp": ts.isoformat(), "equity": float(value)} for ts, value in weekly_equity.items()],
    }


def list_available_datasets(data_dir: Path) -> list[dict[str, str]]:
    """Escanea `data_dir` y devuelve los datasets que realmente existen, parseando el
    símbolo/timeframe de su nombre de archivo. El frontend usa esto para no ofrecer
    combinaciones símbolo+timeframe que van a fallar al correr un backtest."""
    if not data_dir.is_dir():
        return []

    datasets = []
    for path in sorted(data_dir.glob("*.parquet")):
        match = _DATASET_FILENAME_RE.match(path.name)
        if match is None:
            continue
        datasets.append({"symbol": match.group("symbol"), "timeframe": match.group("timeframe"), "dataset": path.name})
    return datasets
