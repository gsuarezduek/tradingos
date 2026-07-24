from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import Strategy, StrategyConfig
from tradingos.optimize.grid import ParameterGrid, expand_grid


@dataclass(slots=True)
class OptimizationResult:
    config: StrategyConfig
    metrics: dict[str, float]


def run_grid_search(
    strategy_cls: type[Strategy],
    base_config: StrategyConfig,
    grid: ParameterGrid,
    data: pd.DataFrame,
    initial_equity: float = 10_000.0,
    rank_by: str = "profit_factor",
) -> list[OptimizationResult]:
    """Corre un backtest por cada combinación de `grid` sobre el mismo `data` (cargado
    una sola vez por el llamador) y devuelve los resultados ordenados descendente por
    `rank_by`."""
    results = []
    for config in expand_grid(base_config, grid):
        strategy = strategy_cls(config)
        engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=initial_equity)
        result = engine.run(data)
        results.append(OptimizationResult(config=config, metrics=result.metrics))

    results.sort(key=lambda r: r.metrics.get(rank_by, float("-inf")), reverse=True)
    return results
