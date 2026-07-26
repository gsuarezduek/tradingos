from __future__ import annotations

import pandas as pd

from tradingos.core.conditions import Condition, compute_required_emas, evaluate_ema_condition
from tradingos.core.strategy import Strategy, StrategyConfig, StrategyContext, register_strategy
from tradingos.core.types import Side, Signal, SignalAction


@register_strategy("condition_based")
class ConditionBasedStrategy(Strategy):
    """Estrategia genérica: entra cuando se cumplen TODAS las `entry_rules` y sale
    cuando se cumplen TODAS las `exit_rules` (ambas del constructor de condiciones, ver
    core/conditions.py). Si `exit_rules` está vacío no hay salida discrecional — la
    posición solo se cierra por SL/TP/trailing, que el motor aplica de forma
    centralizada igual que para el resto de las estrategias.

    Long-only por ahora (mismo alcance que MovingAverageCrossoverStrategy) y solo la
    categoría EMA es ejecutable; el resto queda validado en la capa de API.
    """

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        # Parseadas una sola vez acá (no en on_bar, que corre por cada barra).
        self._entry_rules = [Condition.model_validate(c) for c in config.entry_rules]
        self._exit_rules = [Condition.model_validate(c) for c in config.exit_rules]

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        return compute_required_emas(data, self._entry_rules + self._exit_rules)

    def on_bar(self, context: StrategyContext) -> Signal | None:
        if context.current_index == 0:
            return None

        if context.position is None:
            if self._entry_rules and all(evaluate_ema_condition(c, context) for c in self._entry_rules):
                return Signal(action=SignalAction.OPEN, side=Side.LONG)
            return None

        if self._exit_rules and all(evaluate_ema_condition(c, context) for c in self._exit_rules):
            return Signal(action=SignalAction.CLOSE)
        return None
