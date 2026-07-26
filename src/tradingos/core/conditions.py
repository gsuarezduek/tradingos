from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from tradingos.core.indicators import ema
from tradingos.core.strategy import StrategyContext

# Únicos tipos de condición que el motor sabe ejecutar hoy. El resto de las categorías
# (RSI, MACD, Volumen, Acción del Precio, ATR, Bollinger, ADX) solo existen como
# metadata de catálogo (ver CONDITION_CATALOG) para que el selector muestre el roadmap
# completo sin tener que rediseñar la UI cuando se implementen.
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
_EMA_CONDITION_PARAMS: dict[str, list[str]] = {c["type"]: c["params"] for c in _EMA_CONDITION_TYPES}

# Catálogo completo servido por GET /strategies/conditions/catalog. Las categorías con
# available=False solo tienen label/params de exhibición: no hay evaluador todavía.
CONDITION_CATALOG: list[dict[str, Any]] = [
    {"category": "ema", "label": "EMA", "available": True, "condition_types": _EMA_CONDITION_TYPES},
    {
        "category": "rsi",
        "label": "RSI",
        "available": False,
        "condition_types": [
            {"type": "rsi_above_70", "label": "RSI > 70", "params": []},
            {"type": "rsi_below_30", "label": "RSI < 30", "params": []},
            {"type": "rsi_above_50", "label": "RSI > 50", "params": []},
            {"type": "rsi_below_50", "label": "RSI < 50", "params": []},
            {"type": "rsi_cross_up_30", "label": "RSI cruza 30 hacia arriba", "params": []},
            {"type": "rsi_cross_down_70", "label": "RSI cruza 70 hacia abajo", "params": []},
            {"type": "rsi_between_40_60", "label": "RSI entre 40 y 60", "params": []},
            {"type": "rsi_increasing", "label": "RSI creciente", "params": []},
            {"type": "rsi_decreasing", "label": "RSI decreciente", "params": []},
        ],
    },
    {
        "category": "macd",
        "label": "MACD",
        "available": False,
        "condition_types": [
            {"type": "macd_above_signal", "label": "MACD > Signal", "params": []},
            {"type": "macd_below_signal", "label": "MACD < Signal", "params": []},
            {"type": "macd_bullish_cross", "label": "Cruce alcista", "params": []},
            {"type": "macd_bearish_cross", "label": "Cruce bajista", "params": []},
            {"type": "macd_histogram_positive", "label": "Histograma positivo", "params": []},
            {"type": "macd_histogram_negative", "label": "Histograma negativo", "params": []},
            {"type": "macd_histogram_increasing", "label": "Histograma creciente", "params": []},
            {"type": "macd_above_zero", "label": "MACD sobre cero", "params": []},
            {"type": "macd_below_zero", "label": "MACD bajo cero", "params": []},
        ],
    },
    {
        "category": "volume",
        "label": "Volumen",
        "available": False,
        "condition_types": [
            {"type": "volume_above_avg_20", "label": "Volumen mayor al promedio de 20 velas", "params": []},
            {"type": "volume_below_avg", "label": "Volumen menor al promedio", "params": []},
            {"type": "volume_2x_avg", "label": "Volumen 2x promedio", "params": []},
            {"type": "volume_increasing", "label": "Volumen creciente", "params": []},
            {"type": "volume_decreasing", "label": "Volumen decreciente", "params": []},
            {"type": "volume_highest_of_10", "label": "Última vela con mayor volumen de las últimas 10", "params": []},
        ],
    },
    {
        "category": "price_action",
        "label": "Acción del Precio",
        "available": False,
        "condition_types": [
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
        ],
    },
    {
        "category": "atr",
        "label": "ATR",
        "available": False,
        "condition_types": [
            {"type": "atr_increasing", "label": "ATR creciente", "params": []},
            {"type": "atr_decreasing", "label": "ATR decreciente", "params": []},
            {"type": "atr_above_avg", "label": "ATR mayor al promedio", "params": []},
            {"type": "atr_below_avg", "label": "ATR menor al promedio", "params": []},
            {"type": "stop_atr_x2", "label": "Stop = ATR × 2", "params": []},
            {"type": "take_profit_atr_x3", "label": "Take Profit = ATR × 3", "params": []},
        ],
    },
    {
        "category": "bollinger",
        "label": "Bollinger",
        "available": False,
        "condition_types": [
            {"type": "touches_upper_band", "label": "Precio toca banda superior", "params": []},
            {"type": "touches_lower_band", "label": "Precio toca banda inferior", "params": []},
            {"type": "leaves_band", "label": "Precio sale de la banda", "params": []},
            {"type": "returns_inside_band", "label": "Precio vuelve dentro de la banda", "params": []},
            {"type": "squeeze", "label": "Bollinger Squeeze", "params": []},
            {"type": "expansion", "label": "Bollinger Expansion", "params": []},
        ],
    },
    {
        "category": "adx",
        "label": "ADX",
        "available": False,
        "condition_types": [
            {"type": "adx_above_25", "label": "ADX > 25", "params": []},
            {"type": "adx_above_40", "label": "ADX > 40", "params": []},
            {"type": "adx_below_20", "label": "ADX < 20", "params": []},
            {"type": "adx_increasing", "label": "ADX creciente", "params": []},
            {"type": "adx_decreasing", "label": "ADX decreciente", "params": []},
            {"type": "di_plus_above_minus", "label": "DI+ > DI-", "params": []},
            {"type": "di_minus_above_plus", "label": "DI- > DI+", "params": []},
        ],
    },
]

_AVAILABLE_CATEGORIES = {c["category"] for c in CONDITION_CATALOG if c["available"]}


class Condition(BaseModel):
    category: str
    condition_type: str
    params: dict[str, float] = {}


def validate_condition(condition: Condition) -> None:
    if condition.category not in _AVAILABLE_CATEGORIES:
        raise ValueError(f"la categoría '{condition.category}' todavía no está disponible (por ahora solo 'ema')")
    required = _EMA_CONDITION_PARAMS.get(condition.condition_type)
    if required is None:
        raise ValueError(f"tipo de condición desconocido para EMA: '{condition.condition_type}'")
    missing = [p for p in required if p not in condition.params]
    if missing:
        raise ValueError(f"faltan parámetros para '{condition.condition_type}': {missing}")


def required_ema_periods(conditions: list[Condition]) -> set[int]:
    periods: set[int] = set()
    for condition in conditions:
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


def compute_required_emas(data, conditions: list[Condition]):  # type: ignore[no-untyped-def]
    """Agrega al DataFrame las columnas ema_<period> que las condiciones referencian."""
    for period in required_ema_periods(conditions):
        data[_ema_col(period)] = ema(data["close"], period)
    return data


def describe_condition(condition: Condition) -> str:
    entry = next(c for c in _EMA_CONDITION_TYPES if c["type"] == condition.condition_type)
    label: str = entry["label"]
    params = condition.params

    def fmt(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else str(value)

    if condition.condition_type in ("price_above", "price_below"):
        return label.replace("EMA", f"EMA{fmt(params['period'])}")
    if condition.condition_type in ("indicator_above", "indicator_below", "cross_above", "cross_below"):
        return (
            label.replace("EMA rápida", f"EMA{fmt(params['period_a'])}").replace(
                "EMA lenta", f"EMA{fmt(params['period_b'])}"
            )
        )
    if condition.condition_type in ("slope_positive", "slope_negative"):
        return label.replace("EMA", f"EMA{fmt(params['period'])}")
    if condition.condition_type == "distance_below_pct":
        return label.replace("EMA", f"EMA{fmt(params['period'])}").replace("X%", f"{fmt(params['threshold_pct'])}%")
    return label


def describe_conditions(conditions: list[Condition]) -> str:
    if not conditions:
        return ""
    return " Y ".join(describe_condition(c) for c in conditions)
