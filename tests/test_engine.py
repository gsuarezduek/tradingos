import pandas as pd
import pytest

import tradingos.strategies  # noqa: F401  (registra ma_crossover)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import get_strategy
from tradingos.strategies.ma_crossover import default_config


def _run_backtest(data: pd.DataFrame):
    strategy_cls = get_strategy("ma_crossover")
    strategy = strategy_cls(default_config())
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)
    return engine.run(data)


def test_engine_produces_at_least_one_trade(synthetic_ohlcv):
    result = _run_backtest(synthetic_ohlcv)
    assert len(result.trades) >= 1


def test_engine_equity_curve_matches_bar_count_after_warmup(synthetic_ohlcv):
    result = _run_backtest(synthetic_ohlcv)
    assert len(result.equity_curve) > 0
    assert result.equity_curve.index.is_monotonic_increasing


def test_engine_is_reproducible(synthetic_ohlcv):
    result_a = _run_backtest(synthetic_ohlcv)
    result_b = _run_backtest(synthetic_ohlcv)

    assert result_a.metrics == result_b.metrics
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    assert len(result_a.trades) == len(result_b.trades)
    for trade_a, trade_b in zip(result_a.trades, result_b.trades):
        assert trade_a.pnl == pytest.approx(trade_b.pnl)
        assert trade_a.entry_price == pytest.approx(trade_b.entry_price)


def test_engine_respects_risk_per_trade_sizing(synthetic_ohlcv):
    result = _run_backtest(synthetic_ohlcv)
    config = default_config()
    for trade in result.trades:
        risked = abs(trade.entry_price - trade.entry_price * (1 - config.stop_loss_pct)) * trade.quantity
        # el riesgo teórico al abrir no debería superar ampliamente el % configurado del equity inicial
        assert risked <= 10_000.0 * config.risk_per_trade * 1.05
