from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class SignalAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class Signal:
    action: SignalAction
    side: Side | None = None


@dataclass(slots=True)
class Fill:
    timestamp: datetime
    side: Side
    price: float
    quantity: float
    commission: float


@dataclass(slots=True)
class Position:
    side: Side
    entry_price: float
    quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop_distance: float | None = None
    trailing_stop_price: float | None = None
    entry_timestamp: datetime | None = None

    def unrealized_pnl(self, price: float) -> float:
        direction = 1 if self.side is Side.LONG else -1
        return (price - self.entry_price) * self.quantity * direction


@dataclass(slots=True)
class Trade:
    side: Side
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: float
    exit_price: float
    quantity: float
    commission: float
    pnl: float = field(init=False)

    def __post_init__(self) -> None:
        direction = 1 if self.side is Side.LONG else -1
        gross = (self.exit_price - self.entry_price) * self.quantity * direction
        self.pnl = gross - self.commission
