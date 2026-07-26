from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel

from tradingos.core.indicators import (
    adx as adx_indicator,
    atr as atr_indicator,
    bollinger_bands,
    ema,
    macd as macd_indicator,
    rsi as rsi_indicator,
)
from tradingos.core.strategy import StrategyContext

# Períodos/ventanas fijos para las categorías sin parámetros expuestos al usuario (RSI,
# Volumen, Acción del Precio, ATR, MACD, Bollinger, ADX): el usuario pidió condiciones
# con umbrales concretos (ej. "RSI > 70"), no un indicador parametrizable como EMA — así
# que los períodos son una constante del motor, no un campo de Condition.params.
_RSI_PERIOD = 14
_ATR_PERIOD = 14
_ATR_AVG_WINDOW = 14
_VOLUME_AVG_WINDOW = 20
_VOLUME_HIGHEST_WINDOW = 10
_PRICE_ACTION_BREAKOUT_WINDOW = 20
_MACD_FAST_PERIOD = 12
_MACD_SLOW_PERIOD = 26
_MACD_SIGNAL_PERIOD = 9
_BOLLINGER_PERIOD = 20
_BOLLINGER_NUM_STD = 2.0
_BOLLINGER_WIDTH_AVG_WINDOW = 20
_ADX_PERIOD = 14

_RSI_COL = f"rsi_{_RSI_PERIOD}"
_ATR_COL = f"atr_{_ATR_PERIOD}"
_ATR_AVG_COL = f"atr_avg_{_ATR_AVG_WINDOW}"
_VOLUME_AVG_COL = f"volume_avg_{_VOLUME_AVG_WINDOW}"
_VOLUME_HIGHEST_COL = f"volume_highest_{_VOLUME_HIGHEST_WINDOW}"
_BREAKOUT_HIGH_COL = f"rolling_high_{_PRICE_ACTION_BREAKOUT_WINDOW}"
_BREAKOUT_LOW_COL = f"rolling_low_{_PRICE_ACTION_BREAKOUT_WINDOW}"
_MACD_LINE_COL = "macd_line"
_MACD_SIGNAL_COL = "macd_signal"
_MACD_HIST_COL = "macd_hist"
_BB_MIDDLE_COL = "bb_middle"
_BB_UPPER_COL = "bb_upper"
_BB_LOWER_COL = "bb_lower"
_BB_WIDTH_COL = "bb_width"
_BB_WIDTH_AVG_COL = f"bb_width_avg_{_BOLLINGER_WIDTH_AVG_WINDOW}"
_ADX_COL = f"adx_{_ADX_PERIOD}"
_DI_PLUS_COL = f"di_plus_{_ADX_PERIOD}"
_DI_MINUS_COL = f"di_minus_{_ADX_PERIOD}"

_EMA_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "price_above", "label": "Precio > EMA", "params": ["period"]},
    {"type": "price_below", "label": "Precio < EMA", "params": ["period"]},
    {"type": "indicator_above", "label": "EMA rápida > EMA lenta", "params": ["period_a", "period_b"]},
    {"type": "indicator_below", "label": "EMA rápida < EMA lenta", "params": ["period_a", "period_b"]},
    {"type": "cross_above", "label": "EMA rápida cruza EMA lenta hacia arriba", "params": ["period_a", "period_b"]},
    {"type": "cross_below", "label": "EMA rápida cruza EMA lenta hacia abajo", "params": ["period_a", "period_b"]},
    {"type": "slope_positive", "label": "EMA con pendiente positiva", "params": ["period", "lookback"]},
    {"type": "slope_negative", "label": "EMA con pendiente negativa", "params": ["period", "lookback"]},
    {"type": "distance_below_pct", "label": "Distancia del precio a la EMA menor a X%", "params": ["period", "threshold_pct"]},
]

_RSI_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "rsi_above_70", "label": "RSI > 70", "params": []},
    {"type": "rsi_below_30", "label": "RSI < 30", "params": []},
    {"type": "rsi_above_50", "label": "RSI > 50", "params": []},
    {"type": "rsi_below_50", "label": "RSI < 50", "params": []},
    {"type": "rsi_cross_up_30", "label": "RSI cruza 30 hacia arriba", "params": []},
    {"type": "rsi_cross_down_70", "label": "RSI cruza 70 hacia abajo", "params": []},
    {"type": "rsi_between_40_60", "label": "RSI entre 40 y 60", "params": []},
    {"type": "rsi_increasing", "label": "RSI creciente", "params": []},
    {"type": "rsi_decreasing", "label": "RSI decreciente", "params": []},
]

_MACD_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "macd_above_signal", "label": "MACD > Signal", "params": []},
    {"type": "macd_below_signal", "label": "MACD < Signal", "params": []},
    {"type": "macd_bullish_cross", "label": "Cruce alcista", "params": []},
    {"type": "macd_bearish_cross", "label": "Cruce bajista", "params": []},
    {"type": "macd_histogram_positive", "label": "Histograma positivo", "params": []},
    {"type": "macd_histogram_negative", "label": "Histograma negativo", "params": []},
    {"type": "macd_histogram_increasing", "label": "Histograma creciente", "params": []},
    {"type": "macd_above_zero", "label": "MACD sobre cero", "params": []},
    {"type": "macd_below_zero", "label": "MACD bajo cero", "params": []},
]

_VOLUME_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "volume_above_avg_20", "label": "Volumen mayor al promedio de 20 velas", "params": []},
    {"type": "volume_below_avg", "label": "Volumen menor al promedio", "params": []},
    {"type": "volume_2x_avg", "label": "Volumen 2x promedio", "params": []},
    {"type": "volume_increasing", "label": "Volumen creciente", "params": []},
    {"type": "volume_decreasing", "label": "Volumen decreciente", "params": []},
    {"type": "volume_highest_of_10", "label": "Última vela con mayor volumen de las últimas 10", "params": []},
]

_PRICE_ACTION_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "breaks_high_20", "label": "Rompe máximo de 20 velas", "params": []},
    {"type": "breaks_low_20", "label": "Rompe mínimo de 20 velas", "params": []},
    {"type": "higher_high", "label": "Higher High", "params": []},
    {"type": "higher_low", "label": "Higher Low", "params": []},
    {"type": "lower_high", "label": "Lower High", "params": []},
    {"type": "lower_low", "label": "Lower Low", "params": []},
    {"type": "bullish_candle", "label": "Vela alcista", "params": []},
    {"type": "bearish_candle", "label": "Vela bajista", "params": []},
    {"type": "close_above_prev_high", "label": "Cierre sobre máximo anterior", "params": []},
    {"type": "close_below_prev_low", "label": "Cierre bajo mínimo anterior", "params": []},
]

# "Stop = ATR × 2" / "Take Profit = ATR × 3" (del pedido original) quedan afuera: no son
# condiciones booleanas evaluables barra a barra sino una fórmula de dimensionamiento de
# SL/TP, que hoy el motor centralizado calcula como % fijo (StrategyConfig.stop_loss_pct/
# take_profit_pct). Un SL/TP dinámico por ATR es una feature de riesgo aparte (tocaría el
# motor), no algo que encaje en el constructor de condiciones — decisión confirmada con
# el usuario.
_ATR_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "atr_increasing", "label": "ATR creciente", "params": []},
    {"type": "atr_decreasing", "label": "ATR decreciente", "params": []},
    {"type": "atr_above_avg", "label": "ATR mayor al promedio", "params": []},
    {"type": "atr_below_avg", "label": "ATR menor al promedio", "params": []},
]

_BOLLINGER_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "touches_upper_band", "label": "Precio toca banda superior", "params": []},
    {"type": "touches_lower_band", "label": "Precio toca banda inferior", "params": []},
    {"type": "leaves_band", "label": "Precio sale de la banda", "params": []},
    {"type": "returns_inside_band", "label": "Precio vuelve dentro de la banda", "params": []},
    {"type": "squeeze", "label": "Bollinger Squeeze", "params": []},
    {"type": "expansion", "label": "Bollinger Expansion", "params": []},
]

_ADX_CONDITION_TYPES: list[dict[str, Any]] = [
    {"type": "adx_above_25", "label": "ADX > 25", "params": []},
    {"type": "adx_above_40", "label": "ADX > 40", "params": []},
    {"type": "adx_below_20", "label": "ADX < 20", "params": []},
    {"type": "adx_increasing", "label": "ADX creciente", "params": []},
    {"type": "adx_decreasing", "label": "ADX decreciente", "params": []},
    {"type": "di_plus_above_minus", "label": "DI+ > DI-", "params": []},
    {"type": "di_minus_above_plus", "label": "DI- > DI+", "params": []},
]

# Catálogo completo servido por GET /strategies/conditions/catalog. Las categorías con
# available=False solo tienen label/params de exhibición: no hay evaluador todavía.
CONDITION_CATALOG: list[dict[str, Any]] = [
    {"category": "ema", "label": "EMA", "available": True, "condition_types": _EMA_CONDITION_TYPES},
    {"category": "rsi", "label": "RSI", "available": True, "condition_types": _RSI_CONDITION_TYPES},
    {"category": "macd", "label": "MACD", "available": True, "condition_types": _MACD_CONDITION_TYPES},
    {"category": "volume", "label": "Volumen", "available": True, "condition_types": _VOLUME_CONDITION_TYPES},
    {
        "category": "price_action",
        "label": "Acción del Precio",
        "available": True,
        "condition_types": _PRICE_ACTION_CONDITION_TYPES,
    },
    {"category": "atr", "label": "ATR", "available": True, "condition_types": _ATR_CONDITION_TYPES},
    {"category": "bollinger", "label": "Bollinger", "available": True, "condition_types": _BOLLINGER_CONDITION_TYPES},
    {"category": "adx", "label": "ADX", "available": True, "condition_types": _ADX_CONDITION_TYPES},
]

_AVAILABLE_CATEGORIES = {c["category"] for c in CONDITION_CATALOG if c["available"]}
_CONDITION_PARAMS_BY_CATEGORY: dict[str, dict[str, list[str]]] = {
    cat["category"]: {t["type"]: t["params"] for t in cat["condition_types"]} for cat in CONDITION_CATALOG
}
_CONDITION_TYPE_LABELS: dict[str, str] = {
    t["type"]: t["label"] for cat in CONDITION_CATALOG for t in cat["condition_types"]
}


class Condition(BaseModel):
    category: str
    condition_type: str
    params: dict[str, float] = {}


def validate_condition(condition: Condition) -> None:
    if condition.category not in _AVAILABLE_CATEGORIES:
        raise ValueError(f"la categoría '{condition.category}' todavía no está disponible")
    required = _CONDITION_PARAMS_BY_CATEGORY.get(condition.category, {}).get(condition.condition_type)
    if required is None:
        raise ValueError(f"tipo de condición desconocido para '{condition.category}': '{condition.condition_type}'")
    missing = [p for p in required if p not in condition.params]
    if missing:
        raise ValueError(f"faltan parámetros para '{condition.condition_type}': {missing}")


def normalize_rule_groups(raw: list) -> list[list[Condition]]:
    """`entry_rules`/`exit_rules` aceptan dos formas: la vieja, una lista plana de
    condiciones (todas en Y — lo único que existía antes de los grupos), y la nueva, una
    lista de grupos donde cada grupo es una lista de condiciones (Y dentro del grupo, O
    entre grupos). Esta función normaliza ambas a la forma nueva, para que el resto del
    motor (evaluación, descripción, cálculo de indicadores) solo tenga que lidiar con una
    representación — así las estrategias guardadas antes de que existieran los grupos
    (forma plana) se siguen evaluando exactamente igual que siempre, como un único grupo.
    """
    if not raw:
        return []
    if isinstance(raw[0], dict):
        # Forma vieja: lista plana de condiciones -> un solo grupo (Y de todas).
        return [[Condition.model_validate(c) for c in raw]]
    return [[Condition.model_validate(c) for c in group] for group in raw]


def validate_rule_groups(groups: list[list[Condition]]) -> None:
    for group in groups:
        seen: list[Condition] = []
        for condition in group:
            validate_condition(condition)
            # Misma categoría+tipo+params repetida dentro de un mismo grupo (Y) es
            # siempre redundante (A Y A = A) — casi siempre un error de tipeo del
            # usuario en el constructor, no algo que alguien quiera a propósito. Entre
            # grupos distintos (O) sí tiene sentido repetir una condición (una
            # sub-condición compartida entre dos alternativas), así que ahí no se valida.
            if condition in seen:
                raise ValueError(
                    f"la condición '{condition.condition_type}' está repetida dentro del mismo grupo"
                )
            seen.append(condition)


def required_ema_periods(conditions: list[Condition]) -> set[int]:
    periods: set[int] = set()
    for condition in conditions:
        if condition.category != "ema":
            continue
        for key in ("period", "period_a", "period_b"):
            if key in condition.params:
                periods.add(int(condition.params[key]))
    return periods


def _ema_col(period: float) -> str:
    return f"ema_{int(period)}"


def evaluate_ema_condition(condition: Condition, context: StrategyContext) -> bool:
    """Evalúa una condición de la categoría EMA contra la barra actual. Devuelve False
    (no True por default) cuando no hay historia suficiente para el lookback pedido —
    mismo criterio conservador que `MovingAverageCrossoverStrategy.on_bar`."""
    params = condition.params
    bar = context.bar
    idx = context.current_index

    if condition.condition_type == "price_above":
        return bool(bar["close"] > bar[_ema_col(params["period"])])
    if condition.condition_type == "price_below":
        return bool(bar["close"] < bar[_ema_col(params["period"])])

    if condition.condition_type in ("indicator_above", "indicator_below", "cross_above", "cross_below"):
        col_a, col_b = _ema_col(params["period_a"]), _ema_col(params["period_b"])
        if condition.condition_type == "indicator_above":
            return bool(bar[col_a] > bar[col_b])
        if condition.condition_type == "indicator_below":
            return bool(bar[col_a] < bar[col_b])
        if idx == 0:
            return False
        prev = context.history.iloc[idx - 1]
        if condition.condition_type == "cross_above":
            return bool(prev[col_a] <= prev[col_b] and bar[col_a] > bar[col_b])
        return bool(prev[col_a] >= prev[col_b] and bar[col_a] < bar[col_b])

    if condition.condition_type in ("slope_positive", "slope_negative"):
        lookback = int(params["lookback"])
        if idx < lookback:
            return False
        col = _ema_col(params["period"])
        past = context.history.iloc[idx - lookback]
        if condition.condition_type == "slope_positive":
            return bool(bar[col] > past[col])
        return bool(bar[col] < past[col])

    if condition.condition_type == "distance_below_pct":
        col = _ema_col(params["period"])
        distance_pct = abs(bar["close"] - bar[col]) / bar["close"] * 100
        return bool(distance_pct < params["threshold_pct"])

    raise ValueError(f"tipo de condición desconocido para EMA: '{condition.condition_type}'")


def evaluate_rsi_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    value = bar[_RSI_COL]
    condition_type = condition.condition_type

    if condition_type == "rsi_above_70":
        return bool(value > 70)
    if condition_type == "rsi_below_30":
        return bool(value < 30)
    if condition_type == "rsi_above_50":
        return bool(value > 50)
    if condition_type == "rsi_below_50":
        return bool(value < 50)
    if condition_type == "rsi_between_40_60":
        return bool(40 <= value <= 60)

    if condition_type in ("rsi_cross_up_30", "rsi_cross_down_70", "rsi_increasing", "rsi_decreasing"):
        if idx == 0:
            return False
        prev_value = context.history.iloc[idx - 1][_RSI_COL]
        if condition_type == "rsi_cross_up_30":
            return bool(prev_value <= 30 and value > 30)
        if condition_type == "rsi_cross_down_70":
            return bool(prev_value >= 70 and value < 70)
        if condition_type == "rsi_increasing":
            return bool(value > prev_value)
        return bool(value < prev_value)

    raise ValueError(f"tipo de condición desconocido para RSI: '{condition_type}'")


def evaluate_volume_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    condition_type = condition.condition_type

    if condition_type == "volume_above_avg_20":
        return bool(bar["volume"] > bar[_VOLUME_AVG_COL])
    if condition_type == "volume_below_avg":
        return bool(bar["volume"] < bar[_VOLUME_AVG_COL])
    if condition_type == "volume_2x_avg":
        return bool(bar["volume"] > 2 * bar[_VOLUME_AVG_COL])
    if condition_type == "volume_highest_of_10":
        return bool(bar["volume"] >= bar[_VOLUME_HIGHEST_COL])

    if condition_type in ("volume_increasing", "volume_decreasing"):
        if idx == 0:
            return False
        prev_volume = context.history.iloc[idx - 1]["volume"]
        if condition_type == "volume_increasing":
            return bool(bar["volume"] > prev_volume)
        return bool(bar["volume"] < prev_volume)

    raise ValueError(f"tipo de condición desconocido para Volumen: '{condition_type}'")


def evaluate_price_action_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    condition_type = condition.condition_type

    if condition_type == "bullish_candle":
        return bool(bar["close"] > bar["open"])
    if condition_type == "bearish_candle":
        return bool(bar["close"] < bar["open"])

    # El resto compara contra la barra anterior (o su ventana de 20 ya calculada hasta
    # esa barra): sin historia previa no hay nada que romper/superar todavía.
    if idx == 0:
        return False
    prev = context.history.iloc[idx - 1]

    if condition_type == "breaks_high_20":
        return bool(bar["high"] > prev[_BREAKOUT_HIGH_COL])
    if condition_type == "breaks_low_20":
        return bool(bar["low"] < prev[_BREAKOUT_LOW_COL])
    if condition_type == "higher_high":
        return bool(bar["high"] > prev["high"])
    if condition_type == "higher_low":
        return bool(bar["low"] > prev["low"])
    if condition_type == "lower_high":
        return bool(bar["high"] < prev["high"])
    if condition_type == "lower_low":
        return bool(bar["low"] < prev["low"])
    if condition_type == "close_above_prev_high":
        return bool(bar["close"] > prev["high"])
    if condition_type == "close_below_prev_low":
        return bool(bar["close"] < prev["low"])

    raise ValueError(f"tipo de condición desconocido para Acción del Precio: '{condition_type}'")


def evaluate_atr_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    condition_type = condition.condition_type

    if condition_type == "atr_above_avg":
        return bool(bar[_ATR_COL] > bar[_ATR_AVG_COL])
    if condition_type == "atr_below_avg":
        return bool(bar[_ATR_COL] < bar[_ATR_AVG_COL])

    if condition_type in ("atr_increasing", "atr_decreasing"):
        if idx == 0:
            return False
        prev_atr = context.history.iloc[idx - 1][_ATR_COL]
        if condition_type == "atr_increasing":
            return bool(bar[_ATR_COL] > prev_atr)
        return bool(bar[_ATR_COL] < prev_atr)

    raise ValueError(f"tipo de condición desconocido para ATR: '{condition_type}'")


def evaluate_macd_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    condition_type = condition.condition_type

    if condition_type == "macd_above_signal":
        return bool(bar[_MACD_LINE_COL] > bar[_MACD_SIGNAL_COL])
    if condition_type == "macd_below_signal":
        return bool(bar[_MACD_LINE_COL] < bar[_MACD_SIGNAL_COL])
    if condition_type == "macd_histogram_positive":
        return bool(bar[_MACD_HIST_COL] > 0)
    if condition_type == "macd_histogram_negative":
        return bool(bar[_MACD_HIST_COL] < 0)
    if condition_type == "macd_above_zero":
        return bool(bar[_MACD_LINE_COL] > 0)
    if condition_type == "macd_below_zero":
        return bool(bar[_MACD_LINE_COL] < 0)

    if condition_type in ("macd_bullish_cross", "macd_bearish_cross", "macd_histogram_increasing"):
        if idx == 0:
            return False
        prev = context.history.iloc[idx - 1]
        if condition_type == "macd_bullish_cross":
            return bool(prev[_MACD_LINE_COL] <= prev[_MACD_SIGNAL_COL] and bar[_MACD_LINE_COL] > bar[_MACD_SIGNAL_COL])
        if condition_type == "macd_bearish_cross":
            return bool(prev[_MACD_LINE_COL] >= prev[_MACD_SIGNAL_COL] and bar[_MACD_LINE_COL] < bar[_MACD_SIGNAL_COL])
        return bool(bar[_MACD_HIST_COL] > prev[_MACD_HIST_COL])

    raise ValueError(f"tipo de condición desconocido para MACD: '{condition_type}'")


def evaluate_bollinger_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    condition_type = condition.condition_type

    if condition_type == "touches_upper_band":
        return bool(bar["high"] >= bar[_BB_UPPER_COL])
    if condition_type == "touches_lower_band":
        return bool(bar["low"] <= bar[_BB_LOWER_COL])
    if condition_type == "leaves_band":
        return bool(bar["close"] > bar[_BB_UPPER_COL] or bar["close"] < bar[_BB_LOWER_COL])
    if condition_type == "squeeze":
        return bool(bar[_BB_WIDTH_COL] < bar[_BB_WIDTH_AVG_COL])
    if condition_type == "expansion":
        return bool(bar[_BB_WIDTH_COL] > bar[_BB_WIDTH_AVG_COL])

    if condition_type == "returns_inside_band":
        if idx == 0:
            return False
        prev = context.history.iloc[idx - 1]
        prev_outside = bool(prev["close"] > prev[_BB_UPPER_COL] or prev["close"] < prev[_BB_LOWER_COL])
        now_inside = bool(bar[_BB_LOWER_COL] <= bar["close"] <= bar[_BB_UPPER_COL])
        return prev_outside and now_inside

    raise ValueError(f"tipo de condición desconocido para Bollinger: '{condition_type}'")


def evaluate_adx_condition(condition: Condition, context: StrategyContext) -> bool:
    bar = context.bar
    idx = context.current_index
    condition_type = condition.condition_type

    if condition_type == "adx_above_25":
        return bool(bar[_ADX_COL] > 25)
    if condition_type == "adx_above_40":
        return bool(bar[_ADX_COL] > 40)
    if condition_type == "adx_below_20":
        return bool(bar[_ADX_COL] < 20)
    if condition_type == "di_plus_above_minus":
        return bool(bar[_DI_PLUS_COL] > bar[_DI_MINUS_COL])
    if condition_type == "di_minus_above_plus":
        return bool(bar[_DI_MINUS_COL] > bar[_DI_PLUS_COL])

    if condition_type in ("adx_increasing", "adx_decreasing"):
        if idx == 0:
            return False
        prev_adx = context.history.iloc[idx - 1][_ADX_COL]
        if condition_type == "adx_increasing":
            return bool(bar[_ADX_COL] > prev_adx)
        return bool(bar[_ADX_COL] < prev_adx)

    raise ValueError(f"tipo de condición desconocido para ADX: '{condition_type}'")


_EVALUATORS = {
    "ema": evaluate_ema_condition,
    "rsi": evaluate_rsi_condition,
    "volume": evaluate_volume_condition,
    "price_action": evaluate_price_action_condition,
    "atr": evaluate_atr_condition,
    "macd": evaluate_macd_condition,
    "bollinger": evaluate_bollinger_condition,
    "adx": evaluate_adx_condition,
}


def evaluate_condition(condition: Condition, context: StrategyContext) -> bool:
    evaluator = _EVALUATORS.get(condition.category)
    if evaluator is None:
        raise ValueError(f"la categoría '{condition.category}' todavía no está disponible")
    return evaluator(condition, context)


def evaluate_rule_groups(groups: list[list[Condition]], context: StrategyContext) -> bool:
    """True si CUALQUIER grupo tiene TODAS sus condiciones cumplidas (O entre grupos, Y
    dentro de cada uno). Con un solo grupo esto es exactamente el Y-de-todas de antes."""
    return any(all(evaluate_condition(c, context) for c in group) for group in groups)


def compute_required_indicators(data: pd.DataFrame, conditions: list[Condition]) -> pd.DataFrame:
    """Agrega al DataFrame las columnas que las condiciones referencian, calculando cada
    indicador una sola vez aunque haya varias condiciones de la misma categoría."""
    categories = {c.category for c in conditions}

    for period in required_ema_periods(conditions):
        data[_ema_col(period)] = ema(data["close"], period)
    if "rsi" in categories:
        data[_RSI_COL] = rsi_indicator(data["close"], _RSI_PERIOD)
    if "volume" in categories:
        data[_VOLUME_AVG_COL] = data["volume"].rolling(window=_VOLUME_AVG_WINDOW, min_periods=_VOLUME_AVG_WINDOW).mean()
        data[_VOLUME_HIGHEST_COL] = (
            data["volume"].rolling(window=_VOLUME_HIGHEST_WINDOW, min_periods=_VOLUME_HIGHEST_WINDOW).max()
        )
    if "price_action" in categories:
        data[_BREAKOUT_HIGH_COL] = (
            data["high"].rolling(window=_PRICE_ACTION_BREAKOUT_WINDOW, min_periods=_PRICE_ACTION_BREAKOUT_WINDOW).max()
        )
        data[_BREAKOUT_LOW_COL] = (
            data["low"].rolling(window=_PRICE_ACTION_BREAKOUT_WINDOW, min_periods=_PRICE_ACTION_BREAKOUT_WINDOW).min()
        )
    if "atr" in categories:
        data[_ATR_COL] = atr_indicator(data["high"], data["low"], data["close"], _ATR_PERIOD)
        data[_ATR_AVG_COL] = data[_ATR_COL].rolling(window=_ATR_AVG_WINDOW, min_periods=_ATR_AVG_WINDOW).mean()
    if "macd" in categories:
        data[_MACD_LINE_COL], data[_MACD_SIGNAL_COL], data[_MACD_HIST_COL] = macd_indicator(
            data["close"], _MACD_FAST_PERIOD, _MACD_SLOW_PERIOD, _MACD_SIGNAL_PERIOD
        )
    if "bollinger" in categories:
        data[_BB_MIDDLE_COL], data[_BB_UPPER_COL], data[_BB_LOWER_COL] = bollinger_bands(
            data["close"], _BOLLINGER_PERIOD, _BOLLINGER_NUM_STD
        )
        data[_BB_WIDTH_COL] = (data[_BB_UPPER_COL] - data[_BB_LOWER_COL]) / data[_BB_MIDDLE_COL]
        data[_BB_WIDTH_AVG_COL] = (
            data[_BB_WIDTH_COL].rolling(window=_BOLLINGER_WIDTH_AVG_WINDOW, min_periods=_BOLLINGER_WIDTH_AVG_WINDOW).mean()
        )
    if "adx" in categories:
        data[_ADX_COL], data[_DI_PLUS_COL], data[_DI_MINUS_COL] = adx_indicator(
            data["high"], data["low"], data["close"], _ADX_PERIOD
        )

    return data


def describe_condition(condition: Condition) -> str:
    if condition.category == "ema":
        entry = next(c for c in _EMA_CONDITION_TYPES if c["type"] == condition.condition_type)
        label: str = entry["label"]
        params = condition.params

        def fmt(value: float) -> str:
            return str(int(value)) if float(value).is_integer() else str(value)

        if condition.condition_type in ("price_above", "price_below"):
            return label.replace("EMA", f"EMA{fmt(params['period'])}")
        if condition.condition_type in ("indicator_above", "indicator_below", "cross_above", "cross_below"):
            return label.replace("EMA rápida", f"EMA{fmt(params['period_a'])}").replace(
                "EMA lenta", f"EMA{fmt(params['period_b'])}"
            )
        if condition.condition_type in ("slope_positive", "slope_negative"):
            return label.replace("EMA", f"EMA{fmt(params['period'])}")
        if condition.condition_type == "distance_below_pct":
            return label.replace("EMA", f"EMA{fmt(params['period'])}").replace("X%", f"{fmt(params['threshold_pct'])}%")
        return label

    # El resto de las categorías disponibles (RSI, Volumen, Acción del Precio, ATR) no
    # tienen parámetros de usuario: el label del catálogo ya es el texto final.
    return _CONDITION_TYPE_LABELS.get(condition.condition_type, condition.condition_type)


def describe_conditions(conditions: list[Condition]) -> str:
    if not conditions:
        return ""
    return " Y ".join(describe_condition(c) for c in conditions)


def describe_rule_groups(groups: list[list[Condition]]) -> str:
    if not groups:
        return ""
    if len(groups) == 1:
        return describe_conditions(groups[0])
    return " O ".join(f"({describe_conditions(group)})" for group in groups)
