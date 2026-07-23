from __future__ import annotations

from tradingos.core.strategy import StrategyConfig
from tradingos.core.types import Position, Side


def position_size(equity: float, entry_price: float, stop_price: float, config: StrategyConfig) -> float:
    """Calcula el tamaño de posición a partir del riesgo por operación (o una cantidad fija)."""
    sizing = config.position_sizing
    if sizing.method == "fixed_quantity":
        if sizing.fixed_quantity is None:
            raise ValueError("position_sizing.method='fixed_quantity' requiere fixed_quantity")
        return sizing.fixed_quantity

    risk_amount = equity * config.risk_per_trade
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        raise ValueError("la distancia al stop debe ser positiva para dimensionar por riesgo")
    return risk_amount / stop_distance


def initial_stop_loss(entry_price: float, side: Side, config: StrategyConfig) -> float | None:
    if config.stop_loss_pct is None:
        return None
    direction = 1 if side is Side.LONG else -1
    return entry_price - direction * entry_price * config.stop_loss_pct


def initial_take_profit(entry_price: float, side: Side, config: StrategyConfig) -> float | None:
    if config.take_profit_pct is None:
        return None
    direction = 1 if side is Side.LONG else -1
    return entry_price + direction * entry_price * config.take_profit_pct


def update_trailing_stop(position: Position, current_price: float, config: StrategyConfig) -> None:
    """Actualiza el trailing stop de la posición in-place; solo se mueve a favor del trade."""
    if config.trailing_stop_pct is None:
        return
    distance = current_price * config.trailing_stop_pct
    if position.side is Side.LONG:
        candidate = current_price - distance
        if position.trailing_stop_price is None or candidate > position.trailing_stop_price:
            position.trailing_stop_price = candidate
    else:
        candidate = current_price + distance
        if position.trailing_stop_price is None or candidate < position.trailing_stop_price:
            position.trailing_stop_price = candidate


def exit_price_hit(position: Position, bar_low: float, bar_high: float) -> float | None:
    """Devuelve el precio de salida si SL, TP o trailing stop se tocaron dentro de la barra.

    Cuando varios niveles caen dentro del rango de la barra se asume el escenario más
    conservador: se ejecuta primero el nivel de stop (pérdida) sobre el de take profit.
    """
    stop_candidates = [p for p in (position.stop_loss, position.trailing_stop_price) if p is not None]

    if position.side is Side.LONG:
        hit = [p for p in stop_candidates if bar_low <= p]
        if hit:
            return min(max(hit), bar_high)
        if position.take_profit is not None and bar_high >= position.take_profit:
            return position.take_profit
    else:
        hit = [p for p in stop_candidates if bar_high >= p]
        if hit:
            return max(min(hit), bar_low)
        if position.take_profit is not None and bar_low <= position.take_profit:
            return position.take_profit

    return None
