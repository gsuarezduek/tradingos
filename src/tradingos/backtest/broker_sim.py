from __future__ import annotations

from dataclasses import dataclass

from tradingos.core.types import Side


@dataclass(frozen=True, slots=True)
class BrokerSimConfig:
    commission_pct: float = 0.001  # 0.1% por lado, comisión tipo Binance spot
    slippage_pct: float = 0.0005  # 0.05% en contra del trade
    latency_bars: int = 1  # barras entre la señal y la ejecución del fill (mínimo 1: la señal se genera al cierre de una barra y se ejecuta en una posterior)

    def __post_init__(self) -> None:
        if self.latency_bars < 1:
            raise ValueError("latency_bars debe ser >= 1")


class SimulatedBroker:
    """Modela comisión, slippage y latencia de forma determinística para que los
    resultados del backtest sean reproducibles."""

    def __init__(self, config: BrokerSimConfig | None = None) -> None:
        self.config = config or BrokerSimConfig()

    def fill_price(self, reference_price: float, side: Side, *, is_entry: bool) -> float:
        """Aplica slippage en contra del trader: peor precio al entrar y al salir."""
        direction = 1 if side is Side.LONG else -1
        if not is_entry:
            direction *= -1
        return reference_price + direction * reference_price * self.config.slippage_pct

    def commission(self, price: float, quantity: float) -> float:
        return price * quantity * self.config.commission_pct
