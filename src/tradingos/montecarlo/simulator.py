from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tradingos.core.types import Trade

_PERCENTILES = (5, 25, 50, 75, 95)


@dataclass(slots=True)
class MonteCarloResult:
    num_simulations: int
    initial_equity: float
    original_metrics: dict[str, float]
    final_equity_percentiles: dict[str, float]
    max_drawdown_percentiles: dict[str, float]
    probability_of_profit: float


def _percentiles(values: np.ndarray) -> dict[str, float]:
    return {f"p{p}": float(np.percentile(values, p)) for p in _PERCENTILES}


def run_monte_carlo(
    trades: list[Trade],
    initial_equity: float,
    original_metrics: dict[str, float],
    num_simulations: int = 1000,
    seed: int | None = None,
) -> MonteCarloResult:
    """Resamplea con reposición los P&L de `trades` (ya calculados por un backtest)
    para estimar qué tan sensible es el resultado al orden/composición exacta de las
    operaciones que ocurrieron, en vez de a la estrategia en sí."""
    if not trades:
        return MonteCarloResult(
            num_simulations=num_simulations,
            initial_equity=initial_equity,
            original_metrics=original_metrics,
            final_equity_percentiles={f"p{p}": initial_equity for p in _PERCENTILES},
            max_drawdown_percentiles={f"p{p}": 0.0 for p in _PERCENTILES},
            probability_of_profit=0.0,
        )

    pnls = np.array([t.pnl for t in trades])
    rng = np.random.default_rng(seed)

    final_equities = np.empty(num_simulations)
    max_drawdowns = np.empty(num_simulations)

    for i in range(num_simulations):
        sample = rng.choice(pnls, size=len(pnls), replace=True)
        equity_curve = initial_equity + np.cumsum(sample)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (running_max - equity_curve) / running_max
        final_equities[i] = equity_curve[-1]
        max_drawdowns[i] = drawdown.max()

    return MonteCarloResult(
        num_simulations=num_simulations,
        initial_equity=initial_equity,
        original_metrics=original_metrics,
        final_equity_percentiles=_percentiles(final_equities),
        max_drawdown_percentiles=_percentiles(max_drawdowns),
        probability_of_profit=float(np.mean(final_equities > initial_equity)),
    )
