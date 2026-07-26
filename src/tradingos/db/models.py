from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    live_trading_sessions: Mapped[list["LiveTradingSession"]] = relationship(
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
    # Arranca en False: hay que habilitarlo explícitamente para poder operar de verdad.
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="broker_connections")
    live_trading_sessions: Mapped[list["LiveTradingSession"]] = relationship(back_populates="broker_connection")


class PaperTradingSession(Base):
    __tablename__ = "paper_trading_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Nullable: sesiones creadas antes de que paper trading pasara a partir siempre de
    # una SavedStrategy quedan sin vínculo (no se backfillea). Toda sesión nueva la
    # requiere — ver CreateSessionRequest en api/routers/paper_trading.py.
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("saved_strategies.id"), nullable=True, index=True)
    # Copia de SavedStrategy.strategy_type al momento de crear la sesión (mismo criterio
    # que config_snapshot en StrategyBacktestRun): resuelve la clase de estrategia para
    # el tick sin depender de que la estrategia guardada siga existiendo o sin cambios.
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
    saved_strategy: Mapped["SavedStrategy | None"] = relationship(back_populates="paper_trading_sessions")
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
    # Texto autogenerado (ver core/conditions.describe_rule_groups) a partir de
    # entry_rules/exit_rules — no se tipea a mano, es solo para mostrar en la UI.
    entry_conditions: Mapped[str] = mapped_column(Text, default="")
    exit_conditions: Mapped[str] = mapped_column(Text, default="")
    # Reglas ejecutables del constructor de condiciones: una lista de grupos (O entre
    # grupos, Y dentro de cada uno — ver core/conditions.py), o por retrocompatibilidad
    # una lista plana de Condition (estrategias guardadas antes de que existieran los
    # grupos; se interpreta como un único grupo, ver normalize_rule_groups). Se mergean
    # en StrategyConfig al correr un backtest — ver _run_and_persist_backtest en
    # api/routers/strategies.py. Vacío = sin condiciones (ma_crossover y estrategias
    # viejas no usan estos campos).
    entry_rules: Mapped[list[Any]] = mapped_column(JSON, default=list)
    exit_rules: Mapped[list[Any]] = mapped_column(JSON, default=list)
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
    # Sin cascade delete: no hay endpoint para borrar una SavedStrategy todavía, y si
    # llegara a agregarse, el historial de paper trading no debería desaparecer con ella.
    paper_trading_sessions: Mapped[list["PaperTradingSession"]] = relationship(back_populates="saved_strategy")
    live_trading_sessions: Mapped[list["LiveTradingSession"]] = relationship(back_populates="saved_strategy")


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
    # Ventana de velas del dataset efectivamente usada; None = todo el histórico
    # disponible (compatibilidad con corridas de antes de que existiera este filtro).
    range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    num_trades: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    equity_curve: Mapped[list[Any]] = mapped_column(JSON)
    # A diferencia de PaperTrade, va como JSON acá y no en tabla propia: cada corrida es
    # un snapshot histórico inmutable, no algo que se re-tickee y reemplace.
    trades: Mapped[list[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    strategy: Mapped["SavedStrategy"] = relationship(back_populates="backtest_runs")


class LiveOrder(Base):
    __tablename__ = "live_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    broker_connection_id: Mapped[int] = mapped_column(ForeignKey("broker_connections.id"), index=True)
    # Null para las órdenes manuales de "Operar Manual"; seteado cuando la orden la
    # generó el motor de trading en vivo (ver live_trading/tick.py) por cuenta propia.
    live_trading_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("live_trading_sessions.id"), nullable=True, index=True
    )
    exchange: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    # Monto en USDT que se pidió gastar (BUY) o liquidar (SELL) — la orden siempre
    # se expresa en USDT, nunca en cantidad del activo base, sin importar el lado.
    amount_usdt: Mapped[float] = mapped_column(Float)
    # Cantidad del activo base y precio promedio que el exchange informó como
    # realmente ejecutados — null si la orden fue rechazada o si el exchange no lo
    # informó en la respuesta (ver connectors.bitget.place_market_order).
    filled_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "submitted" (el exchange la aceptó) o "rejected" (el exchange la rechazó,
    # ver error_message) — no es un tracker de fills/ciclo de vida completo.
    status: Mapped[str] = mapped_column(String(16))
    exchange_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    live_trading_session: Mapped["LiveTradingSession | None"] = relationship(back_populates="orders")


class LiveTradingSession(Base):
    """Una SavedStrategy operando sola contra una cuenta real (trading_enabled=True).

    A diferencia de PaperTradingSession, el tick no puede "recalcular todo de nuevo":
    una orden real ya ejecutada es irreversible. El motor (live_trading/tick.py) resuelve
    esto re-corriendo el motor de backtest sobre la misma ventana que paper trading, pero
    solo actúa sobre la diferencia entre `current_position` (lo que de verdad tenemos
    abierto) y lo que el replay dice que debería estar abierto ahora — ver el docstring
    del módulo para el detalle y las limitaciones conocidas.
    """

    __tablename__ = "live_trading_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("saved_strategies.id"), index=True)
    broker_connection_id: Mapped[int] = mapped_column(ForeignKey("broker_connections.id"), index=True)
    # Copias al momento de crear la sesión (mismo criterio que PaperTradingSession.strategy
    # y StrategyBacktestRun.config_snapshot): la sesión no cambia de comportamiento si la
    # estrategia o la conexión se editan después.
    exchange: Mapped[str] = mapped_column(String(32))
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # Lo que la sesión cree tener realmente abierto en el exchange ahora mismo:
    # {side, entry_price, quantity, stop_loss, take_profit, entry_timestamp, opened_at}.
    # entry_timestamp es la marca de la barra simulada (no el reloj real) — es la clave
    # de identidad que el tick usa para saber si sigue siendo "la misma" posición entre
    # corridas; opened_at sí es el timestamp real en que se mandó la orden. Null si está flat.
    current_position: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="live_trading_sessions")
    saved_strategy: Mapped["SavedStrategy"] = relationship(back_populates="live_trading_sessions")
    broker_connection: Mapped["BrokerConnection"] = relationship(back_populates="live_trading_sessions")
    orders: Mapped[list["LiveOrder"]] = relationship(back_populates="live_trading_session")
    trades: Mapped[list["LiveTrade"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class LiveTrade(Base):
    """Operación real ya cerrada por una LiveTradingSession — mismo shape que PaperTrade,
    pero entry_timestamp/exit_timestamp acá son tiempos reales (cuándo se mandaron las
    órdenes), no marcas de barra simulada."""

    __tablename__ = "live_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("live_trading_sessions.id"), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)

    session: Mapped["LiveTradingSession"] = relationship(back_populates="trades")
