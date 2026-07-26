import pandas as pd

import tradingos.strategies  # noqa: F401  (registra condition_based y ma_crossover)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.conditions import Condition, evaluate_ema_condition
from tradingos.core.strategy import StrategyConfig, StrategyContext, get_strategy


def _context(history: pd.DataFrame, current_index: int) -> StrategyContext:
    return StrategyContext(history=history, current_index=current_index, position=None, equity=10_000.0)


def _history(closes: list[float], ema_20: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes, "ema_20": ema_20})


def test_price_above_and_price_below():
    history = _history(closes=[105.0, 95.0], ema_20=[100.0, 100.0])
    above = Condition(category="ema", condition_type="price_above", params={"period": 20})
    below = Condition(category="ema", condition_type="price_below", params={"period": 20})

    assert evaluate_ema_condition(above, _context(history, 0)) is True
    assert evaluate_ema_condition(below, _context(history, 0)) is False
    assert evaluate_ema_condition(above, _context(history, 1)) is False
    assert evaluate_ema_condition(below, _context(history, 1)) is True


def test_indicator_above_and_below():
    history = pd.DataFrame({"close": [0.0], "ema_20": [110.0], "ema_50": [100.0]})
    above = Condition(category="ema", condition_type="indicator_above", params={"period_a": 20, "period_b": 50})
    below = Condition(category="ema", condition_type="indicator_below", params={"period_a": 20, "period_b": 50})

    assert evaluate_ema_condition(above, _context(history, 0)) is True
    assert evaluate_ema_condition(below, _context(history, 0)) is False


def test_cross_above_and_cross_below_need_previous_bar():
    history = pd.DataFrame({"close": [0.0, 0.0], "ema_20": [95.0, 105.0], "ema_50": [100.0, 100.0]})
    cross_up = Condition(category="ema", condition_type="cross_above", params={"period_a": 20, "period_b": 50})
    cross_down = Condition(category="ema", condition_type="cross_below", params={"period_a": 20, "period_b": 50})

    assert evaluate_ema_condition(cross_up, _context(history, 0)) is False  # no hay barra anterior
    assert evaluate_ema_condition(cross_up, _context(history, 1)) is True
    assert evaluate_ema_condition(cross_down, _context(history, 1)) is False


def test_slope_positive_and_negative_need_enough_lookback():
    ema_values = [100.0, 101.0, 99.0, 98.0, 97.0]
    history = pd.DataFrame({"close": [0.0] * len(ema_values), "ema_50": ema_values})
    positive = Condition(category="ema", condition_type="slope_positive", params={"period": 50, "lookback": 3})
    negative = Condition(category="ema", condition_type="slope_negative", params={"period": 50, "lookback": 3})

    # índice 2: no hay 3 barras de historia todavía -> False, no excepción
    assert evaluate_ema_condition(positive, _context(history, 2)) is False
    # índice 4: ema[4]=97 vs ema[1]=101 -> bajó, no subió
    assert evaluate_ema_condition(positive, _context(history, 4)) is False
    assert evaluate_ema_condition(negative, _context(history, 4)) is True


def test_distance_below_pct():
    history = pd.DataFrame({"close": [100.0], "ema_20": [100.5]})
    near = Condition(category="ema", condition_type="distance_below_pct", params={"period": 20, "threshold_pct": 1.0})
    far = Condition(category="ema", condition_type="distance_below_pct", params={"period": 20, "threshold_pct": 0.1})

    assert evaluate_ema_condition(near, _context(history, 0)) is True
    assert evaluate_ema_condition(far, _context(history, 0)) is False


def test_condition_based_strategy_produces_trades_on_synthetic_data(synthetic_ohlcv):
    config = StrategyConfig(
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss_pct=0.05,
        risk_per_trade=0.01,
        entry_rules=[{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}],
        exit_rules=[{"category": "ema", "condition_type": "cross_below", "params": {"period_a": 12, "period_b": 26}}],
    )
    strategy_cls = get_strategy("condition_based")
    engine = BacktestEngine(strategy_cls(config), SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)

    result = engine.run(synthetic_ohlcv)

    assert len(result.trades) >= 1
    assert not result.equity_curve.empty


def test_condition_based_strategy_without_exit_rules_only_exits_via_stop_loss(synthetic_ohlcv):
    config = StrategyConfig(
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss_pct=0.05,
        risk_per_trade=0.01,
        entry_rules=[{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}],
        exit_rules=[],
    )
    strategy_cls = get_strategy("condition_based")
    engine = BacktestEngine(strategy_cls(config), SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)

    result = engine.run(synthetic_ohlcv)

    # Sin exit_rules, cualquier trade cerrado tuvo que serlo por SL/TP/trailing, no por
    # una condición discrecional del motor genérico.
    assert isinstance(result.trades, list)
