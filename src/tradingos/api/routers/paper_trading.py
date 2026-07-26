from __future__ import annotations

import time
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.backtest.engine import SUPPORTED_TIMEFRAMES
from tradingos.core.strategy import StrategyConfig
from tradingos.data.binance_downloader import fetch_spot_symbols
from tradingos.db.models import PaperTrade, PaperTradingSession, SavedStrategy, User
from tradingos.db.session import get_db
from tradingos.paper_trading.tick import run_tick_for_session

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])

# La lista de símbolos de Binance (~2000+) cambia con muy poca frecuencia; cachearla
# evita pegarle a Binance en cada tecla que el usuario tipea en el autocomplete.
_SYMBOLS_CACHE_TTL_SECONDS = 3600
_symbols_cache: dict[str, Any] = {"symbols": None, "fetched_at": 0.0}


def _get_cached_symbols() -> list[str]:
    now = time.time()
    if _symbols_cache["symbols"] is None or now - _symbols_cache["fetched_at"] > _SYMBOLS_CACHE_TTL_SECONDS:
        _symbols_cache["symbols"] = fetch_spot_symbols()
        _symbols_cache["fetched_at"] = now
    return _symbols_cache["symbols"]


class CreateSessionRequest(BaseModel):
    strategy_id: int
    symbol: str
    timeframe: str
    initial_equity: float = 10_000.0


class SessionResponse(BaseModel):
    id: int
    strategy_id: int | None
    # Nombre de la SavedStrategy al momento de listar (no un snapshot: si el usuario la
    # renombra después, acá se ve el nombre actual). None si la sesión es de antes de
    # que paper trading se enganchara al Constructor, o si la estrategia ya no existe.
    strategy_name: str | None
    strategy: str
    symbol: str
    timeframe: str
    status: str
    config: dict[str, Any]
    initial_equity: float
    current_equity: float
    open_position: dict[str, Any] | None
    last_tick_at: str | None
    created_at: str


class TradeResponse(BaseModel):
    side: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    quantity: float
    commission: float
    pnl: float


class SessionDetailResponse(SessionResponse):
    equity_curve: list[dict[str, Any]]
    trades: list[TradeResponse]


def _to_session_response(session: PaperTradingSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        strategy_id=session.strategy_id,
        strategy_name=session.saved_strategy.name if session.saved_strategy else None,
        strategy=session.strategy,
        symbol=session.symbol,
        timeframe=session.timeframe,
        status=session.status,
        config=session.config,
        initial_equity=session.initial_equity,
        current_equity=session.current_equity,
        open_position=session.open_position,
        last_tick_at=session.last_tick_at.isoformat() if session.last_tick_at else None,
        created_at=session.created_at.isoformat(),
    )


def _get_owned_session(session_id: int, user: User, db: Session) -> PaperTradingSession:
    session = (
        db.query(PaperTradingSession)
        .filter(PaperTradingSession.id == session_id, PaperTradingSession.user_id == user.id)
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


@router.get("/symbols", response_model=list[str])
def list_symbols(user: User = Depends(get_current_user)) -> list[str]:
    try:
        return _get_cached_symbols()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"no se pudo obtener la lista de símbolos de Binance: {exc}") from exc


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    request: CreateSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionResponse:
    if request.timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"temporalidad no soportada: {request.timeframe} (soportadas: {sorted(SUPPORTED_TIMEFRAMES)})",
        )

    strategy = _get_owned_strategy(request.strategy_id, user, db)
    if strategy.status != "active":
        raise HTTPException(
            status_code=400,
            detail="la estrategia está pausada — activala en Estrategias antes de crear una sesión de Paper Trading",
        )
    if request.symbol not in strategy.symbols:
        raise HTTPException(status_code=400, detail=f"'{request.symbol}' no está entre los mercados de la estrategia")
    if request.timeframe not in strategy.timeframes:
        raise HTTPException(status_code=400, detail=f"'{request.timeframe}' no está entre las temporalidades de la estrategia")

    existing_active = (
        db.query(PaperTradingSession)
        .filter(
            PaperTradingSession.strategy_id == strategy.id,
            PaperTradingSession.symbol == request.symbol,
            PaperTradingSession.timeframe == request.timeframe,
            PaperTradingSession.status == "active",
        )
        .first()
    )
    if existing_active is not None:
        raise HTTPException(
            status_code=400,
            detail="ya hay una sesión de paper trading activa con esta estrategia, símbolo y timeframe",
        )

    # Mismo merge que _run_and_persist_backtest en api/routers/strategies.py: la config
    # base de la estrategia + symbol/timeframe elegidos para esta sesión + sus reglas de
    # entrada/salida (si es una estrategia por condiciones).
    effective_config = StrategyConfig.model_validate(
        {
            **strategy.config,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "entry_rules": strategy.entry_rules,
            "exit_rules": strategy.exit_rules,
        }
    )

    # Sin límite de sesiones activas simultáneas por usuario: cada una corre
    # independiente en el tick del cron (run_all_active ya itera todas las activas).
    session = PaperTradingSession(
        user_id=user.id,
        strategy_id=strategy.id,
        strategy=strategy.strategy_type,
        symbol=request.symbol,
        timeframe=request.timeframe,
        config=effective_config.model_dump(),
        initial_equity=request.initial_equity,
        current_equity=request.initial_equity,
        equity_curve=[],
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Corre el primer tick al toque (no hace falta esperar al cron) y de paso valida el
    # símbolo/config contra Binance: si falla, no dejamos una sesión rota creada.
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
        db.query(PaperTradingSession)
        .filter(PaperTradingSession.user_id == user.id)
        .order_by(PaperTradingSession.created_at.desc())
        .all()
    )
    return [_to_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def session_detail(
    session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionDetailResponse:
    session = _get_owned_session(session_id, user, db)
    trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.session_id == session.id)
        .order_by(PaperTrade.exit_timestamp)
        .all()
    )
    return SessionDetailResponse(
        **_to_session_response(session).model_dump(),
        equity_curve=session.equity_curve,
        trades=[
            TradeResponse(
                side=t.side,
                entry_timestamp=t.entry_timestamp.isoformat(),
                exit_timestamp=t.exit_timestamp.isoformat(),
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                quantity=t.quantity,
                commission=t.commission,
                pnl=t.pnl,
            )
            for t in trades
        ],
    )


@router.post("/sessions/{session_id}/stop", response_model=SessionResponse)
def stop_session(
    session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionResponse:
    session = _get_owned_session(session_id, user, db)
    session.status = "stopped"
    db.commit()
    db.refresh(session)
    return _to_session_response(session)
