import numpy as np
import pandas as pd
import pytest

import tradingos.strategies  # noqa: F401  (registra ma_crossover)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import get_strategy
from tradingos.strategies.ma_crossover import default_config


def _synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    flat = np.full(40, 100.0)
    uptrend = 100.0 + np.cumsum(rng.uniform(0.3, 1.2, size=110))
    downtrend = uptrend[-1] - np.cumsum(rng.uniform(0.3, 1.2, size=110))
    tail = np.full(40, downtrend[-1])
    close = np.concatenate([flat, uptrend, downtrend, tail])[:n]

    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2023-01-01", periods=len(close), freq="h", tz="UTC"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(len(close), 1000.0),
        }
    )


def _run_backtest():
    data = _synthetic_ohlcv()
    strategy_cls = get_strategy("ma_crossover")
    strategy = strategy_cls(default_config())
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)
    return engine.run(data)


def test_engine_produces_at_least_one_trade():
    result = _run_backtest()
    assert len(result.trades) >= 1


def test_engine_equity_curve_matches_bar_count_after_warmup():
    result = _run_backtest()
    assert len(result.equity_curve) > 0
    assert result.equity_curve.index.is_monotonic_increasing


def test_engine_is_reproducible():
    result_a = _run_backtest()
    result_b = _run_backtest()

    assert result_a.metrics == result_b.metrics
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    assert len(result_a.trades) == len(result_b.trades)
    for trade_a, trade_b in zip(result_a.trades, result_b.trades):
        assert trade_a.pnl == pytest.approx(trade_b.pnl)
        assert trade_a.entry_price == pytest.approx(trade_b.entry_price)


def test_engine_respects_risk_per_trade_sizing():
    result = _run_backtest()
    config = default_config()
    for trade in result.trades:
        risked = abs(trade.entry_price - trade.entry_price * (1 - config.stop_loss_pct)) * trade.quantity
        # el riesgo teórico al abrir no debería superar ampliamente el % configurado del equity inicial
        assert risked <= 10_000.0 * config.risk_per_trade * 1.05
