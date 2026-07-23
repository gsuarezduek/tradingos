from __future__ import annotations

import pandas as pd

from tradingos.core.indicators import atr, ema
from tradingos.core.strategy import PositionSizing, Strategy, StrategyConfig, StrategyContext, register_strategy
from tradingos.core.types import Side, Signal, SignalAction


def default_config(symbol: str = "BTCUSDT", timeframe: str = "1h") -> StrategyConfig:
    return StrategyConfig(
        symbol=symbol,
        timeframe=timeframe,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        trailing_stop_pct=0.015,
        risk_per_trade=0.01,
        position_sizing=PositionSizing(method="risk_fraction"),
        indicators={
            "ema_fast": {"period": 12},
            "ema_slow": {"period": 26},
            "atr": {"period": 14, "min_value_pct": 0.001},
        },
    )


@register_strategy("ma_crossover")
class MovingAverageCrossoverStrategy(Strategy):
    """Cruce de EMAs (long-only) con filtro de volatilidad mínima por ATR.

    Entrada: EMA rápida cruza por encima de la EMA lenta y el ATR supera el mínimo
    configurado (evita operar en mercados demasiado planos).
    Salida discrecional: EMA rápida cruza por debajo de la EMA lenta.
    SL, TP, trailing stop y el tamaño de posición los aplica el motor de backtesting
    de forma centralizada, a partir de `config`.
    """

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        fast_period = self.config.indicators["ema_fast"]["period"]
        slow_period = self.config.indicators["ema_slow"]["period"]
        atr_period = self.config.indicators["atr"]["period"]

        data["ema_fast"] = ema(data["close"], fast_period)
        data["ema_slow"] = ema(data["close"], slow_period)
        data["atr"] = atr(data["high"], data["low"], data["close"], atr_period)
        return data

    def on_bar(self, context: StrategyContext) -> Signal | None:
        if context.current_index == 0:
            return None

        bar = context.bar
        prev = context.history.iloc[context.current_index - 1]
        min_atr = bar["close"] * self.config.indicators["atr"]["min_value_pct"]

        crossed_up = prev["ema_fast"] <= prev["ema_slow"] and bar["ema_fast"] > bar["ema_slow"]
        crossed_down = prev["ema_fast"] >= prev["ema_slow"] and bar["ema_fast"] < bar["ema_slow"]

        if context.position is None:
            if crossed_up and bar["atr"] >= min_atr:
                return Signal(action=SignalAction.OPEN, side=Side.LONG)
            return None

        if crossed_down:
            return Signal(action=SignalAction.CLOSE)
        return None
