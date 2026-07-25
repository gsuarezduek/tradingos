from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    broker_connections: Mapped[list["BrokerConnection"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    paper_trading_sessions: Mapped[list["PaperTradingSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_strategies: Mapped[list["SavedStrategy"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class BrokerConnection(Base):
    __tablename__ = "broker_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exchange: Mapped[str] = mapped_column(String(32), default="binance")
    label: Mapped[str] = mapped_column(String(100))
    # Cifrados con Fernet (ver db/crypto.py); nunca se guarda el plaintext.
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    api_secret_encrypted: Mapped[str] = mapped_column(Text)
    # Solo la usan exchanges que la requieren (ej. Bitget); null para el resto.
    passphrase_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="broker_connections")


class PaperTradingSession(Base):
    __tablename__ = "paper_trading_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    # StrategyConfig.model_dump() completo — se reconstruye tal cual en cada tick.
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    initial_equity: Mapped[float] = mapped_column(Float)
    current_equity: Mapped[float] = mapped_column(Float)
    # Últimos ~200 puntos [{"timestamp": iso, "equity": float}, ...] para graficar.
    equity_curve: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # Snapshot de la posición abierta al último tick (side/entry_price/quantity/...), o
    # null si está flat. Se pisa entero en cada tick, no se acumula historial.
    open_position: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="paper_trading_sessions")
    trades: Mapped[list["PaperTrade"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("paper_trading_sessions.id"), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)

    session: Mapped["PaperTradingSession"] = relationship(back_populates="trades")


class SavedStrategy(Base):
    __tablename__ = "saved_strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    strategy_type: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    # Mercados y temporalidades donde el usuario declara que la estrategia aplica; son
    # metadata declarativa y no implican que exista dataset para correr un backtest —
    # eso se valida aparte contra los datasets realmente disponibles.
    symbols: Mapped[list[str]] = mapped_column(JSON)
    timeframes: Mapped[list[str]] = mapped_column(JSON)
    # Texto libre, no un DSL ejecutable: hoy la lógica de entrada/salida vive fija en el
    # código de la estrategia registrada (Strategy.on_bar), esto es solo documentación.
    entry_conditions: Mapped[str] = mapped_column(Text, default="")
    exit_conditions: Mapped[str] = mapped_column(Text, default="")
    # StrategyConfig.model_dump() base (SL/TP/trailing/riesgo/indicadores); cada corrida
    # de backtest puede pisar symbol/timeframe pero parte de esta config.
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="saved_strategies")
    backtest_runs: Mapped[list["StrategyBacktestRun"]] = relationship(
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyBacktestRun.created_at.desc()",
    )


class StrategyBacktestRun(Base):
    __tablename__ = "strategy_backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("saved_strategies.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    dataset: Mapped[str] = mapped_column(String(120))
    # Config exacta usada en esta corrida (symbol/timeframe incluidos): si la estrategia
    # se edita después, el historial no debe cambiar retroactivamente.
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    initial_equity: Mapped[float] = mapped_column(Float)
    num_trades: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    equity_curve: Mapped[list[Any]] = mapped_column(JSON)
    # A diferencia de PaperTrade, va como JSON acá y no en tabla propia: cada corrida es
    # un snapshot histórico inmutable, no algo que se re-tickee y reemplace.
    trades: Mapped[list[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    strategy: Mapped["SavedStrategy"] = relationship(back_populates="backtest_runs")
