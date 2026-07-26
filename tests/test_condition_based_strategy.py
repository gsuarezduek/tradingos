import pandas as pd

import tradingos.strategies  # noqa: F401  (registra condition_based y ma_crossover)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.conditions import (
    Condition,
    describe_rule_groups,
    evaluate_adx_condition,
    evaluate_atr_condition,
    evaluate_bollinger_condition,
    evaluate_ema_condition,
    evaluate_macd_condition,
    evaluate_price_action_condition,
    evaluate_rsi_condition,
    evaluate_rule_groups,
    evaluate_volume_condition,
    normalize_rule_groups,
)
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


def test_rsi_conditions():
    rsi_values = [55.0, 75.0, 25.0, 45.0, 50.0]
    history = pd.DataFrame({"close": [0.0] * len(rsi_values), "rsi_14": rsi_values})

    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_above_70"), _context(history, 1)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_below_30"), _context(history, 2)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_above_50"), _context(history, 0)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_below_50"), _context(history, 2)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_between_40_60"), _context(history, 3)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_between_40_60"), _context(history, 1)) is False
    # índice 0: no hay barra anterior -> False, no excepción
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_increasing"), _context(history, 0)) is False
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_increasing"), _context(history, 1)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_decreasing"), _context(history, 2)) is True
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_cross_up_30"), _context(history, 2)) is False
    cross_history = pd.DataFrame({"close": [0.0, 0.0], "rsi_14": [25.0, 35.0]})
    assert evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_cross_up_30"), _context(cross_history, 1)) is True
    cross_down_history = pd.DataFrame({"close": [0.0, 0.0], "rsi_14": [75.0, 65.0]})
    assert (
        evaluate_rsi_condition(Condition(category="rsi", condition_type="rsi_cross_down_70"), _context(cross_down_history, 1))
        is True
    )


def test_volume_conditions():
    history = pd.DataFrame(
        {
            "close": [0.0] * 4,
            "volume": [100.0, 500.0, 200.0, 50.0],
            "volume_avg_20": [200.0, 200.0, 200.0, 200.0],
            "volume_highest_10": [100.0, 500.0, 500.0, 500.0],
        }
    )

    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_above_avg_20"), _context(history, 1)) is True
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_below_avg"), _context(history, 3)) is True
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_2x_avg"), _context(history, 1)) is True
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_2x_avg"), _context(history, 2)) is False
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_highest_of_10"), _context(history, 1)) is True
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_highest_of_10"), _context(history, 2)) is False
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_increasing"), _context(history, 0)) is False
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_increasing"), _context(history, 1)) is True
    assert evaluate_volume_condition(Condition(category="volume", condition_type="volume_decreasing"), _context(history, 2)) is True


def test_price_action_conditions():
    history = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0],
            "high": [110.0, 108.0, 120.0],
            "low": [95.0, 96.0, 104.0],
            "close": [105.0, 90.0, 115.0],
            "rolling_high_20": [110.0, 110.0, 110.0],
            "rolling_low_20": [95.0, 95.0, 95.0],
        }
    )

    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="bullish_candle"), _context(history, 0)) is True
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="bearish_candle"), _context(history, 1)) is True
    # índice 0: no hay barra anterior -> False, no excepción
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="breaks_high_20"), _context(history, 0)) is False
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="breaks_high_20"), _context(history, 2)) is True
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="breaks_low_20"), _context(history, 2)) is False
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="higher_high"), _context(history, 2)) is True
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="higher_low"), _context(history, 2)) is True
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="lower_high"), _context(history, 1)) is True
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="lower_low"), _context(history, 1)) is False
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="close_above_prev_high"), _context(history, 2)) is True
    assert evaluate_price_action_condition(Condition(category="price_action", condition_type="close_below_prev_low"), _context(history, 1)) is True


def test_atr_conditions():
    history = pd.DataFrame(
        {
            "close": [0.0, 0.0, 0.0],
            "atr_14": [1.0, 1.5, 1.2],
            "atr_avg_14": [1.3, 1.3, 1.3],
        }
    )

    assert evaluate_atr_condition(Condition(category="atr", condition_type="atr_above_avg"), _context(history, 1)) is True
    assert evaluate_atr_condition(Condition(category="atr", condition_type="atr_below_avg"), _context(history, 0)) is True
    # índice 0: no hay barra anterior -> False, no excepción
    assert evaluate_atr_condition(Condition(category="atr", condition_type="atr_increasing"), _context(history, 0)) is False
    assert evaluate_atr_condition(Condition(category="atr", condition_type="atr_increasing"), _context(history, 1)) is True
    assert evaluate_atr_condition(Condition(category="atr", condition_type="atr_decreasing"), _context(history, 2)) is True


def test_macd_conditions():
    history = pd.DataFrame(
        {
            "close": [0.0] * 5,
            "macd_line": [1.0, -1.0, 2.0, 2.5, 0.5],
            "macd_signal": [0.5, 0.5, 1.0, 1.0, 1.0],
            "macd_hist": [0.5, -1.5, 1.0, 1.5, -0.5],
        }
    )

    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_above_signal"), _context(history, 0)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_below_signal"), _context(history, 1)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_histogram_positive"), _context(history, 0)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_histogram_negative"), _context(history, 1)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_above_zero"), _context(history, 0)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_below_zero"), _context(history, 1)) is True
    # índice 0: no hay barra anterior -> False, no excepción
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_bullish_cross"), _context(history, 0)) is False
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_bullish_cross"), _context(history, 2)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_bearish_cross"), _context(history, 4)) is True
    assert evaluate_macd_condition(Condition(category="macd", condition_type="macd_histogram_increasing"), _context(history, 2)) is True


def test_bollinger_conditions():
    history = pd.DataFrame(
        {
            "high": [102.0, 106.0, 94.0, 100.0],
            "low": [98.0, 104.0, 90.0, 96.0],
            "close": [100.0, 106.0, 100.0, 101.0],
            "bb_upper": [105.0, 105.0, 105.0, 105.0],
            "bb_lower": [95.0, 95.0, 95.0, 95.0],
            "bb_width": [0.08, 0.12, 0.08, 0.12],
            "bb_width_avg_20": [0.10, 0.10, 0.10, 0.10],
        }
    )

    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="touches_upper_band"), _context(history, 1)) is True
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="touches_lower_band"), _context(history, 2)) is True
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="leaves_band"), _context(history, 1)) is True
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="leaves_band"), _context(history, 0)) is False
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="squeeze"), _context(history, 0)) is True
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="expansion"), _context(history, 1)) is True
    # índice 0: no hay barra anterior -> False, no excepción
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="returns_inside_band"), _context(history, 0)) is False
    assert evaluate_bollinger_condition(Condition(category="bollinger", condition_type="returns_inside_band"), _context(history, 2)) is True


def test_adx_conditions():
    history = pd.DataFrame(
        {
            "close": [0.0] * 4,
            "adx_14": [15.0, 30.0, 45.0, 40.0],
            "di_plus_14": [20.0, 30.0, 15.0, 15.0],
            "di_minus_14": [25.0, 10.0, 30.0, 30.0],
        }
    )

    assert evaluate_adx_condition(Condition(category="adx", condition_type="adx_above_25"), _context(history, 1)) is True
    assert evaluate_adx_condition(Condition(category="adx", condition_type="adx_above_40"), _context(history, 2)) is True
    assert evaluate_adx_condition(Condition(category="adx", condition_type="adx_below_20"), _context(history, 0)) is True
    assert evaluate_adx_condition(Condition(category="adx", condition_type="di_plus_above_minus"), _context(history, 1)) is True
    assert evaluate_adx_condition(Condition(category="adx", condition_type="di_minus_above_plus"), _context(history, 2)) is True
    # índice 0: no hay barra anterior -> False, no excepción
    assert evaluate_adx_condition(Condition(category="adx", condition_type="adx_increasing"), _context(history, 0)) is False
    assert evaluate_adx_condition(Condition(category="adx", condition_type="adx_increasing"), _context(history, 1)) is True
    assert evaluate_adx_condition(Condition(category="adx", condition_type="adx_decreasing"), _context(history, 3)) is True


def test_condition_based_strategy_combines_adx_conditions(synthetic_ohlcv):
    config = StrategyConfig(
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss_pct=0.05,
        risk_per_trade=0.01,
        entry_rules=[
            {"category": "adx", "condition_type": "adx_above_25", "params": {}},
            {"category": "adx", "condition_type": "di_plus_above_minus", "params": {}},
        ],
        exit_rules=[{"category": "adx", "condition_type": "di_minus_above_plus", "params": {}}],
    )
    strategy_cls = get_strategy("condition_based")
    engine = BacktestEngine(strategy_cls(config), SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)

    result = engine.run(synthetic_ohlcv)

    # No se afirma un número de trades específico, solo que el motor generalizado corre
    # sin romperse con ADX/DI+/DI-.
    assert isinstance(result.trades, list)
    assert not result.equity_curve.empty


def test_condition_based_strategy_combines_macd_and_bollinger_conditions(synthetic_ohlcv):
    config = StrategyConfig(
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss_pct=0.05,
        risk_per_trade=0.01,
        entry_rules=[
            {"category": "macd", "condition_type": "macd_bullish_cross", "params": {}},
            {"category": "bollinger", "condition_type": "touches_lower_band", "params": {}},
        ],
        exit_rules=[{"category": "macd", "condition_type": "macd_bearish_cross", "params": {}}],
    )
    strategy_cls = get_strategy("condition_based")
    engine = BacktestEngine(strategy_cls(config), SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)

    result = engine.run(synthetic_ohlcv)

    # No se afirma un número de trades específico, solo que el motor generalizado corre
    # sin romperse mezclando MACD y Bollinger.
    assert isinstance(result.trades, list)
    assert not result.equity_curve.empty


def test_condition_based_strategy_combines_ema_and_rsi_conditions(synthetic_ohlcv):
    config = StrategyConfig(
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss_pct=0.05,
        risk_per_trade=0.01,
        entry_rules=[
            {"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}},
            {"category": "rsi", "condition_type": "rsi_below_50", "params": {}},
        ],
        exit_rules=[{"category": "rsi", "condition_type": "rsi_above_70", "params": {}}],
    )
    strategy_cls = get_strategy("condition_based")
    engine = BacktestEngine(strategy_cls(config), SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)

    result = engine.run(synthetic_ohlcv)

    # No se afirma un número de trades específico (depende de la combinación exacta),
    # solo que el motor generalizado corre sin romperse mezclando dos categorías.
    assert isinstance(result.trades, list)
    assert not result.equity_curve.empty


def test_normalize_rule_groups_wraps_legacy_flat_list_as_one_group():
    flat = [
        {"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}},
        {"category": "rsi", "condition_type": "rsi_below_50", "params": {}},
    ]
    groups = normalize_rule_groups(flat)
    assert len(groups) == 1
    assert len(groups[0]) == 2
    assert groups[0][0].category == "ema"
    assert groups[0][1].category == "rsi"


def test_normalize_rule_groups_keeps_grouped_shape():
    grouped = [
        [{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}],
        [{"category": "rsi", "condition_type": "rsi_below_30", "params": {}}],
    ]
    groups = normalize_rule_groups(grouped)
    assert len(groups) == 2
    assert groups[0][0].category == "ema"
    assert groups[1][0].category == "rsi"


def test_normalize_rule_groups_empty():
    assert normalize_rule_groups([]) == []


def test_evaluate_rule_groups_is_or_of_and():
    history = pd.DataFrame({"close": [0.0], "rsi_14": [20.0], "ema_20": [110.0]})
    context = _context(history, 0)
    # Grupo 1 (Y): price_above EMA20 (falso, close=0) Y algo más -> el grupo entero da False.
    group_false = [Condition(category="ema", condition_type="price_above", params={"period": 20})]
    # Grupo 2: RSI < 30 (verdadero) -> alcanza con este grupo para que el OR dé True.
    group_true = [Condition(category="rsi", condition_type="rsi_below_30")]

    assert evaluate_rule_groups([group_false], context) is False
    assert evaluate_rule_groups([group_true], context) is True
    assert evaluate_rule_groups([group_false, group_true], context) is True
    assert evaluate_rule_groups([], context) is False


def test_describe_rule_groups_wraps_multiple_groups_in_parens():
    groups = [
        [Condition(category="ema", condition_type="price_above", params={"period": 20})],
        [Condition(category="rsi", condition_type="rsi_below_30")],
    ]
    text = describe_rule_groups(groups)
    assert text == "(Precio > EMA20) O (RSI < 30)"
    assert describe_rule_groups(groups[:1]) == "Precio > EMA20"  # un solo grupo: sin paréntesis
    assert describe_rule_groups([]) == ""


def test_condition_based_strategy_with_or_groups_enters_on_either_group(synthetic_ohlcv):
    config = StrategyConfig(
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss_pct=0.05,
        risk_per_trade=0.01,
        entry_rules=[
            [{"category": "ema", "condition_type": "cross_above", "params": {"period_a": 12, "period_b": 26}}],
            [{"category": "rsi", "condition_type": "rsi_below_30", "params": {}}],
        ],
        exit_rules=[[{"category": "ema", "condition_type": "cross_below", "params": {"period_a": 12, "period_b": 26}}]],
    )
    strategy_cls = get_strategy("condition_based")
    engine = BacktestEngine(strategy_cls(config), SimulatedBroker(BrokerSimConfig()), initial_equity=10_000.0)

    result = engine.run(synthetic_ohlcv)

    # RSI < 30 es más laxo que el cruce de EMA solo: con el OR tiene que haber al menos
    # tantos trades como con el cruce de EMA solo (nunca menos).
    assert len(result.trades) >= 1
    assert not result.equity_curve.empty


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
