from __future__ import annotations

import numpy as np
import pandas as pd

from tradingos.core.types import Trade


def profit_factor(trades: list[Trade]) -> float:
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in trades if t.pnl < 0)
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def win_rate(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > 0)
    return wins / len(trades)


def expectancy(trades: list[Trade]) -> float:
    """PnL promedio por operación (en unidades monetarias)."""
    if not trades:
        return 0.0
    return sum(t.pnl for t in trades) / len(trades)


def max_drawdown(equity_curve: pd.Series) -> float:
    """Máxima caída desde un pico previo, como fracción (0.2 = -20%)."""
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    return float(-drawdown.min())


def _periodic_returns(equity_curve: pd.Series) -> pd.Series:
    return equity_curve.pct_change().dropna()


def sharpe_ratio(equity_curve: pd.Series, periods_per_year: float, risk_free_rate: float = 0.0) -> float:
    returns = _periodic_returns(equity_curve)
    if returns.empty or returns.std(ddof=0) == 0:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    return float(excess.mean() / returns.std(ddof=0) * np.sqrt(periods_per_year))


def sortino_ratio(equity_curve: pd.Series, periods_per_year: float, risk_free_rate: float = 0.0) -> float:
    returns = _periodic_returns(equity_curve)
    if returns.empty:
        return 0.0
    downside = returns[returns < 0]
    downside_std = downside.std(ddof=0)
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    return float(excess.mean() / downside_std * np.sqrt(periods_per_year))


def cagr(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    start_value, end_value = equity_curve.iloc[0], equity_curve.iloc[-1]
    if start_value <= 0:
        return 0.0
    years = (equity_curve.index[-1] - equity_curve.index[0]).total_seconds() / (365.25 * 24 * 3600)
    if years <= 0:
        return 0.0
    return float((end_value / start_value) ** (1 / years) - 1)


def avg_monthly_return(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    monthly = equity_curve.resample("ME").last().dropna()
    monthly_returns = monthly.pct_change().dropna()
    if monthly_returns.empty:
        return 0.0
    return float(monthly_returns.mean())


def avg_risk_per_trade(trades: list[Trade], initial_equity: float) -> float:
    """Pérdida promedio de las operaciones perdedoras, como fracción del equity inicial.

    Es una aproximación al riesgo realmente asumido por operación (no el riesgo
    configurado a priori en la estrategia).
    """
    losses = [-t.pnl for t in trades if t.pnl < 0]
    if not losses or initial_equity <= 0:
        return 0.0
    return float(np.mean(losses) / initial_equity)


def compute_metrics(trades: list[Trade], equity_curve: pd.Series, periods_per_year: float) -> dict[str, float]:
    initial_equity = float(equity_curve.iloc[0]) if not equity_curve.empty else 0.0
    return {
        "profit_factor": profit_factor(trades),
        "win_rate": win_rate(trades),
        "expectancy": expectancy(trades),
        "max_drawdown": max_drawdown(equity_curve),
        "sharpe_ratio": sharpe_ratio(equity_curve, periods_per_year),
        "sortino_ratio": sortino_ratio(equity_curve, periods_per_year),
        "cagr": cagr(equity_curve),
        "avg_monthly_return": avg_monthly_return(equity_curve),
        "avg_risk_per_trade": avg_risk_per_trade(trades, initial_equity),
        "num_trades": len(trades),
    }
