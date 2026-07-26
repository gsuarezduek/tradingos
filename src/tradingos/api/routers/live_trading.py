from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.backtest.engine import SUPPORTED_TIMEFRAMES
from tradingos.core.strategy import StrategyConfig
from tradingos.data.binance_downloader import INTERVAL_MS
from tradingos.db.models import BrokerConnection, LiveOrder, LiveTrade, LiveTradingSession, SavedStrategy, User
from tradingos.db.session import get_db
from tradingos.live_trading.tick import run_tick_for_session

router = APIRouter(prefix="/live-trading", tags=["live-trading"])

# El cron de trading en vivo corre cada 15 minutos (scripts/run_live_trading_tick.py,
# configurado en Railway). Una temporalidad más rápida que eso es riesgosa acá aunque no
# lo sea en paper trading: una operación que abre y cierra completa entre dos ticks nunca
# pasa por el motor de reconciliación como "actualmente abierta" y se pierde en silencio
# (ver el docstring de run_tick_for_session en live_trading/tick.py). Mientras el cron no
# corra más seguido, no se puede ofrecer nada más rápido que esto acá.
_MIN_LIVE_TRADING_INTERVAL_MS = 15 * 60_000

# Trading Automático no tiene todavía ningún límite de riesgo agregado (exposición total,
# drawdown diario, etc.) — este es el primero y más simple: un tope duro de sesiones
# activas simultáneas por usuario, para que activar estrategias sin pensarlo dos veces no
# termine en un número sin control de cuentas operando plata real a la vez. No es
# configurable por usuario a propósito: es una baranda de seguridad del sistema, no una
# preferencia.
MAX_ACTIVE_LIVE_TRADING_SESSIONS = 5

# Temporalidades que se pueden activar en Trading Automático, derivadas del piso de
# arriba — única fuente de verdad para esto. El frontend las consume vía /limits en vez
# de reimplementar el cálculo (antes tenía su propia tabla de minutos por temporalidad,
# que se podía desincronizar del piso real del backend).
ELIGIBLE_LIVE_TRADING_TIMEFRAMES = sorted(
    (tf for tf in SUPPORTED_TIMEFRAMES if INTERVAL_MS[tf] >= _MIN_LIVE_TRADING_INTERVAL_MS),
    key=lambda tf: INTERVAL_MS[tf],
)


class LimitsResponse(BaseModel):
    eligible_timeframes: list[str]


class CreateSessionRequest(BaseModel):
    strategy_id: int
    broker_connection_id: int
    symbol: str
    timeframe: str


class OrderSummary(BaseModel):
    id: int
    side: str
    amount_usdt: float
    filled_quantity: float | None
    avg_price: float | None
    status: str
    error_message: str | None
    created_at: str


class TradeSummary(BaseModel):
    side: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float


class SessionResponse(BaseModel):
    id: int
    strategy_id: int
    strategy_name: str
    strategy: str
    broker_connection_id: int
    broker_connection_label: str
    exchange: str
    symbol: str
    timeframe: str
    status: str
    config: dict[str, Any]
    current_position: dict[str, Any] | None
    last_tick_at: str | None
    created_at: str


class SessionDetailResponse(SessionResponse):
    trades: list[TradeSummary]
    orders: list[OrderSummary]


def _to_session_response(session: LiveTradingSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        strategy_id=session.strategy_id,
        strategy_name=session.saved_strategy.name,
        strategy=session.strategy,
        broker_connection_id=session.broker_connection_id,
        broker_connection_label=session.broker_connection.label,
        exchange=session.exchange,
        symbol=session.symbol,
        timeframe=session.timeframe,
        status=session.status,
        config=session.config,
        current_position=session.current_position,
        last_tick_at=session.last_tick_at.isoformat() if session.last_tick_at else None,
        created_at=session.created_at.isoformat(),
    )


def _get_owned_session(session_id: int, user: User, db: Session) -> LiveTradingSession:
    session = (
        db.query(LiveTradingSession)
        .filter(LiveTradingSession.id == session_id, LiveTradingSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="sesión no encontrada")
    return session


def _get_owned_strategy(strategy_id: int, user: User, db: Session) -> SavedStrategy:
    strategy = (
        db.query(SavedStrategy).filter(SavedStrategy.id == strategy_id, SavedStrategy.user_id == user.id).first()
    )
    if strategy is None:
        raise HTTPException(status_code=404, detail="estrategia no encontrada")
    return strategy


def _get_owned_connection(connection_id: int, user: User, db: Session) -> BrokerConnection:
    connection = (
        db.query(BrokerConnection)
        .filter(BrokerConnection.id == connection_id, BrokerConnection.user_id == user.id)
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="conexión no encontrada")
    return connection


@router.get("/limits", response_model=LimitsResponse)
def limits(user: User = Depends(get_current_user)) -> LimitsResponse:
    return LimitsResponse(eligible_timeframes=ELIGIBLE_LIVE_TRADING_TIMEFRAMES)


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    request: CreateSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionResponse:
    if request.timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"temporalidad no soportada: {request.timeframe} (soportadas: {sorted(SUPPORTED_TIMEFRAMES)})",
        )
    if INTERVAL_MS[request.timeframe] < _MIN_LIVE_TRADING_INTERVAL_MS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{request.timeframe}' es más rápida que el intervalo del cron de trading en vivo (15m) — "
                "una operación podría abrir y cerrar sin que el sistema la vea nunca. Usá 15m o una "
                "temporalidad mayor, o paper-tradeala mientras tanto."
            ),
        )

    strategy = _get_owned_strategy(request.strategy_id, user, db)
    connection = _get_owned_connection(request.broker_connection_id, user, db)

    if strategy.status != "active":
        raise HTTPException(
            status_code=400,
            detail="la estrategia está pausada — activala en Estrategias antes de crear una sesión de Trading Automático",
        )
    if not connection.trading_enabled:
        raise HTTPException(
            status_code=403,
            detail="esta conexión no tiene trading habilitado — activalo primero en Conexión con Exchanges",
        )
    if request.symbol not in strategy.symbols:
        raise HTTPException(status_code=400, detail=f"'{request.symbol}' no está entre los mercados de la estrategia")
    if request.timeframe not in strategy.timeframes:
        raise HTTPException(
            status_code=400, detail=f"'{request.timeframe}' no está entre las temporalidades de la estrategia"
        )

    # Sin esto, un doble click (o activarla dos veces por error) abre dos sesiones
    # independientes operando la misma cuenta real en paralelo, cada una calculando su
    # propio tamaño de posición sin saber de la otra — duplica la exposición real.
    existing_active = (
        db.query(LiveTradingSession)
        .filter(
            LiveTradingSession.strategy_id == strategy.id,
            LiveTradingSession.symbol == request.symbol,
            LiveTradingSession.broker_connection_id == connection.id,
            LiveTradingSession.status == "active",
        )
        .first()
    )
    if existing_active is not None:
        raise HTTPException(
            status_code=400,
            detail="ya hay una sesión activa con esta estrategia, símbolo y cuenta — detenela antes de crear otra",
        )

    active_sessions_count = (
        db.query(LiveTradingSession)
        .filter(LiveTradingSession.user_id == user.id, LiveTradingSession.status == "active")
        .count()
    )
    if active_sessions_count >= MAX_ACTIVE_LIVE_TRADING_SESSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"ya tenés {MAX_ACTIVE_LIVE_TRADING_SESSIONS} sesiones de Trading Automático activas — es el "
                "máximo permitido por ahora. Detené alguna antes de activar una nueva."
            ),
        )

    # Mismo merge que paper trading / _run_and_persist_backtest en api/routers/strategies.py.
    effective_config = StrategyConfig.model_validate(
        {
            **strategy.config,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "entry_rules": strategy.entry_rules,
            "exit_rules": strategy.exit_rules,
        }
    )

    session = LiveTradingSession(
        user_id=user.id,
        strategy_id=strategy.id,
        broker_connection_id=connection.id,
        exchange=connection.exchange,
        strategy=strategy.strategy_type,
        symbol=request.symbol,
        timeframe=request.timeframe,
        config=effective_config.model_dump(),
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Corre el primer tick al toque, mismo espíritu que paper trading: si falla (símbolo
    # inválido, credenciales rotas, etc.) no dejamos una sesión rota creada.
    try:
        run_tick_for_session(db, session)
    except Exception as exc:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=400, detail=f"no se pudo iniciar la sesión: {exc}") from exc

    return _to_session_response(session)


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SessionResponse]:
    sessions = (
        db.query(LiveTradingSession)
        .filter(LiveTradingSession.user_id == user.id)
        .order_by(LiveTradingSession.created_at.desc())
        .all()
    )
    return [_to_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def session_detail(
    session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionDetailResponse:
    session = _get_owned_session(session_id, user, db)
    trades = (
        db.query(LiveTrade).filter(LiveTrade.session_id == session.id).order_by(LiveTrade.exit_timestamp).all()
    )
    orders = (
        db.query(LiveOrder)
        .filter(LiveOrder.live_trading_session_id == session.id)
        .order_by(LiveOrder.created_at.desc())
        .all()
    )
    return SessionDetailResponse(
        **_to_session_response(session).model_dump(),
        trades=[
            TradeSummary(
                side=t.side,
                entry_timestamp=t.entry_timestamp.isoformat(),
                exit_timestamp=t.exit_timestamp.isoformat(),
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                quantity=t.quantity,
                pnl=t.pnl,
            )
            for t in trades
        ],
        orders=[
            OrderSummary(
                id=o.id,
                side=o.side,
                amount_usdt=o.amount_usdt,
                filled_quantity=o.filled_quantity,
                avg_price=o.avg_price,
                status=o.status,
                error_message=o.error_message,
                created_at=o.created_at.isoformat(),
            )
            for o in orders
        ],
    )


@router.post("/sessions/{session_id}/stop", response_model=SessionResponse)
def stop_session(
    session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionResponse:
    """Detiene la sesión (deja de tickear). Si hay una posición real abierta, NO la
    cierra automáticamente — sigue siendo una posición real en la cuenta del usuario;
    cerrarla es una decisión que le corresponde a él, no al sistema."""
    session = _get_owned_session(session_id, user, db)
    session.status = "stopped"
    db.commit()
    db.refresh(session)
    return _to_session_response(session)
