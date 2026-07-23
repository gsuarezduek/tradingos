import pandas as pd
import pytest

from tradingos.core.strategy import Strategy, StrategyConfig, StrategyContext, get_strategy, list_strategies, register_strategy
from tradingos.core.types import Signal


def test_register_and_get_strategy():
    @register_strategy("test_dummy_strategy")
    class DummyStrategy(Strategy):
        def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
            return data

        def on_bar(self, context: StrategyContext) -> Signal | None:
            return None

    assert "test_dummy_strategy" in list_strategies()
    assert get_strategy("test_dummy_strategy") is DummyStrategy


def test_duplicate_registration_raises():
    @register_strategy("test_dummy_strategy_2")
    class DummyStrategy2(Strategy):
        def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
            return data

        def on_bar(self, context: StrategyContext) -> Signal | None:
            return None

    with pytest.raises(ValueError):

        @register_strategy("test_dummy_strategy_2")
        class DummyStrategy3(Strategy):
            def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
                return data

            def on_bar(self, context: StrategyContext) -> Signal | None:
                return None


def test_get_unknown_strategy_raises_key_error():
    with pytest.raises(KeyError):
        get_strategy("does_not_exist")


def test_risk_fraction_requires_stop_loss_pct():
    with pytest.raises(ValueError):
        StrategyConfig(symbol="BTCUSDT", timeframe="1h")
