from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tradingos.core.types import Trade


@dataclass(slots=True)
class BacktestResult:
    equity_curve: pd.Series
    trades: list[Trade]
    metrics: dict[str, float]

    def summary(self) -> str:
        lines = [f"Trades: {len(self.trades)}"]
        for key, value in self.metrics.items():
            if key == "num_trades":
                continue
            lines.append(f"  {key}: {value:.4f}")
        return "\n".join(lines)
