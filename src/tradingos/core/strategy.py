from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from tradingos.core.types import Position, Signal


class PositionSizing(BaseModel):
    """Cómo se calcula el tamaño de posición a partir del riesgo por operación."""

    method: str = Field(default="risk_fraction", description="risk_fraction | fixed_quantity")
    fixed_quantity: float | None = None


class StrategyConfig(BaseModel):
    """Campos declarativos que toda estrategia debe definir (ver documento de visión)."""

    symbol: str
    timeframe: str
    stop_loss_pct: float | None = Field(default=None, description="Distancia de SL como fracción del precio de entrada")
    take_profit_pct: float | None = Field(default=None, description="Distancia de TP como fracción del precio de entrada")
    trailing_stop_pct: float | None = Field(default=None, description="Distancia de trailing stop como fracción del precio")
    risk_per_trade: float = Field(default=0.01, gt=0, le=1, description="Fracción del equity arriesgada por operación")
    position_sizing: PositionSizing = Field(default_factory=PositionSizing)
    indicators: dict[str, dict[str, Any]] = Field(default_factory=dict, description="nombre -> parámetros del indicador")

    @field_validator("stop_loss_pct", "take_profit_pct", "trailing_stop_pct")
    @classmethod
    def _positive_if_set(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("debe ser un valor positivo")
        return v

    @model_validator(mode="after")
    def _risk_fraction_needs_stop_loss(self) -> "StrategyConfig":
        if self.position_sizing.method == "risk_fraction" and self.stop_loss_pct is None:
            raise ValueError("position_sizing.method='risk_fraction' requiere stop_loss_pct para poder dimensionar por riesgo")
        return self


class StrategyContext:
    """Vista de solo lectura del estado del mercado y de la posición en la barra actual.

    `history` es el DataFrame completo con indicadores ya calculados; `current_index`
    marca la barra actual. Se expone así (en vez de recortar el DataFrame en cada barra)
    para que consultar el pasado sea O(1) y no O(n) por barra.
    """

    __slots__ = ("history", "current_index", "position", "equity")

    def __init__(self, history: pd.DataFrame, current_index: int, position: Position | None, equity: float) -> None:
        self.history = history
        self.current_index = current_index
        self.position = position
        self.equity = equity

    @property
    def bar(self) -> pd.Series:
        return self.history.iloc[self.current_index]


class Strategy(ABC):
    """Clase base para todas las estrategias. Las nuevas estrategias solo la subclasean
    y se registran con @register_strategy; el motor de backtesting nunca se modifica."""

    config: ClassVar[StrategyConfig]

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @abstractmethod
    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        """Recibe el OHLCV crudo y devuelve el DataFrame con los indicadores agregados."""

    @abstractmethod
    def on_bar(self, context: StrategyContext) -> Signal | None:
        """Se llama en cada barra. Devuelve una Signal de apertura/cierre o None."""


_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(name: str):
    def decorator(cls: type[Strategy]) -> type[Strategy]:
        if name in _REGISTRY:
            raise ValueError(f"ya existe una estrategia registrada con el nombre '{name}'")
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_strategy(name: str) -> type[Strategy]:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"no hay ninguna estrategia registrada con el nombre '{name}'") from exc


def list_strategies() -> list[str]:
    return sorted(_REGISTRY)
