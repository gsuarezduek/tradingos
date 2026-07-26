from __future__ import annotations

import pandas as pd

from tradingos.core.conditions import compute_required_indicators, evaluate_rule_groups, normalize_rule_groups
from tradingos.core.strategy import Strategy, StrategyConfig, StrategyContext, register_strategy
from tradingos.core.types import Side, Signal, SignalAction


@register_strategy("condition_based")
class ConditionBasedStrategy(Strategy):
    """Estrategia genérica: entra cuando CUALQUIER grupo de `entry_rules` tiene TODAS
    sus condiciones cumplidas (O entre grupos, Y dentro de cada uno — el constructor de
    condiciones, ver core/conditions.py), y sale con la misma lógica sobre `exit_rules`.
    Si `exit_rules` está vacío no hay salida discrecional — la posición solo se cierra
    por SL/TP/trailing, que el motor aplica de forma centralizada igual que para el
    resto de las estrategias.

    Long-only por ahora (mismo alcance que MovingAverageCrossoverStrategy). Las
    categorías disponibles hoy son EMA, RSI, Volumen, Acción del Precio, ATR, MACD,
    Bollinger y ADX; el resto queda validado en la capa de API.
    """

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        # Parseadas una sola vez acá (no en on_bar, que corre por cada barra).
        # normalize_rule_groups acepta tanto la forma vieja (lista plana, todas en Y)
        # como la nueva (lista de grupos) — ver su docstring.
        self._entry_groups = normalize_rule_groups(config.entry_rules)
        self._exit_groups = normalize_rule_groups(config.exit_rules)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        all_conditions = [c for group in self._entry_groups + self._exit_groups for c in group]
        return compute_required_indicators(data, all_conditions)

    def on_bar(self, context: StrategyContext) -> Signal | None:
        if context.current_index == 0:
            return None

        if context.position is None:
            if self._entry_groups and evaluate_rule_groups(self._entry_groups, context):
                return Signal(action=SignalAction.OPEN, side=Side.LONG)
            return None

        if self._exit_groups and evaluate_rule_groups(self._exit_groups, context):
            return Signal(action=SignalAction.CLOSE)
        return None
