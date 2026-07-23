import pandas as pd
import pytest

from tradingos.backtest.metrics import (
    avg_risk_per_trade,
    cagr,
    expectancy,
    max_drawdown,
    profit_factor,
    win_rate,
)
from tradingos.core.types import Side, Trade

TS = pd.Timestamp("2024-01-01", tz="UTC")


def _trade(pnl_by_price: tuple[float, float], quantity: float = 1.0) -> Trade:
    entry, exit_ = pnl_by_price
    return Trade(
        side=Side.LONG,
        entry_timestamp=TS,
        exit_timestamp=TS + pd.Timedelta(hours=1),
        entry_price=entry,
        exit_price=exit_,
        quantity=quantity,
        commission=0.0,
    )


def test_profit_factor():
    trades = [_trade((100, 110)), _trade((100, 90))]  # +10, -10
    assert profit_factor(trades) == pytest.approx(1.0)


def test_profit_factor_no_losses_is_inf():
    trades = [_trade((100, 110))]
    assert profit_factor(trades) == float("inf")


def test_profit_factor_no_trades_is_zero():
    assert profit_factor([]) == 0.0


def test_win_rate():
    trades = [_trade((100, 110)), _trade((100, 90)), _trade((100, 105))]
    assert win_rate(trades) == pytest.approx(2 / 3)


def test_expectancy():
    trades = [_trade((100, 110)), _trade((100, 90))]  # +10, -10
    assert expectancy(trades) == pytest.approx(0.0)


def test_max_drawdown():
    equity = pd.Series([100, 120, 90, 110], index=pd.date_range("2024-01-01", periods=4, freq="D"))
    # pico 120 -> valle 90 => -25%
    assert max_drawdown(equity) == pytest.approx(0.25)


def test_max_drawdown_monotonic_up_is_zero():
    equity = pd.Series([100, 110, 120], index=pd.date_range("2024-01-01", periods=3, freq="D"))
    assert max_drawdown(equity) == pytest.approx(0.0)


def test_cagr_doubling_in_one_year():
    idx = pd.DatetimeIndex([pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")])
    equity = pd.Series([100.0, 200.0], index=idx)
    assert cagr(equity) == pytest.approx(1.0, rel=1e-2)


def test_avg_risk_per_trade():
    trades = [_trade((100, 90)), _trade((100, 80))]  # pérdidas de 10 y 20
    assert avg_risk_per_trade(trades, initial_equity=1000) == pytest.approx(15 / 1000)
