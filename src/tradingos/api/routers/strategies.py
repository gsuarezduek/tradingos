from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.backtest.engine import SUPPORTED_TIMEFRAMES
from tradingos.backtest.service import DATA_DIR, list_available_datasets, resolve_dataset, resolve_strategy, run_backtest_result
from tradingos.core.strategy import StrategyConfig, get_strategy, list_strategies
from tradingos.db.models import SavedStrategy, StrategyBacktestRun, User
from tradingos.db.session import get_db

router = APIRouter(prefix="/strategies", tags=["strategies"])

Category = Literal["scalping", "day_trading", "swing"]
Status = Literal["active", "paused"]


class CreateStrategyRequest(BaseModel):
    name: str
    strategy_type: str = "ma_crossover"
    category: Category
    symbols: list[str] = Field(min_length=1)
    timeframes: list[str] = Field(min_length=1)
    entry_conditions: str = ""
    exit_conditions: str = ""
    config: StrategyConfig
    notes: str = ""
    initial_equity: float = 10_000.0


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    category: Category | None = None
    symbols: list[str] | None = Field(default=None, min_length=1)
    timeframes: list[str] | None = Field(default=None, min_length=1)
    entry_conditions: str | None = None
    exit_conditions: str | None = None
    config: StrategyConfig | None = None
    status: Status | None = None
    notes: str | None = None


class RunBacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    initial_equity: float = 10_000.0


class BacktestRunSummary(BaseModel):
    id: int
    symbol: str
    timeframe: str
    dataset: str
    initial_equity: float
    num_trades: int
    metrics: dict[str, Any]
    created_at: str


class BacktestRunDetail(BacktestRunSummary):
    config_snapshot: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]


class StrategyResponse(BaseModel):
    id: int
    name: str
    strategy_type: str
    category: str
    symbols: list[str]
    timeframes: list[str]
    entry_conditions: str
    exit_conditions: str
    config: dict[str, Any]
    status: str
    notes: str
    created_at: str
    updated_at: str
    # Resumen de la corrida más reciente (o None si por alguna razón no hay ninguna);
    # así el listado puede mostrar win rate/PnL sin pedir el detalle de cada estrategia.
    latest_run: BacktestRunSummary | None


class StrategyDetailResponse(StrategyResponse):
    backtest_runs: list[BacktestRunSummary]


def _to_strategy_response(strategy: SavedStrategy) -> StrategyResponse:
    latest_run = strategy.backtest_runs[0] if strategy.backtest_runs else None
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        strategy_type=strategy.strategy_type,
        category=strategy.category,
        symbols=strategy.symbols,
        timeframes=strategy.timeframes,
        entry_conditions=strategy.entry_conditions,
        exit_conditions=strategy.exit_conditions,
        config=strategy.config,
        status=strategy.status,
        notes=strategy.notes,
        created_at=strategy.created_at.isoformat(),
        updated_at=strategy.updated_at.isoformat(),
        latest_run=_to_run_summary(latest_run) if latest_run else None,
    )


def _to_run_summary(run: StrategyBacktestRun) -> BacktestRunSummary:
    return BacktestRunSummary(
        id=run.id,
        symbol=run.symbol,
        timeframe=run.timeframe,
        dataset=run.dataset,
        initial_equity=run.initial_equity,
        num_trades=run.num_trades,
        metrics=run.metrics,
        created_at=run.created_at.isoformat(),
    )


def _get_owned_strategy(strategy_id: int, user: User, db: Session) -> SavedStrategy:
    strategy = (
        db.query(SavedStrategy).filter(SavedStrategy.id == strategy_id, SavedStrategy.user_id == user.id).first()
    )
    if strategy is None:
        raise HTTPException(status_code=404, detail="estrategia no encontrada")
    return strategy


def _validate_timeframes(timeframes: list[str]) -> None:
    unsupported = sorted(set(timeframes) - SUPPORTED_TIMEFRAMES)
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"temporalidades no soportadas: {', '.join(unsupported)} (soportadas: {sorted(SUPPORTED_TIMEFRAMES)})",
        )


def _resolve_run_dataset(symbol: str, timeframe: str) -> str:
    """Valida que exista un dataset real para symbol+timeframe y devuelve su nombre de
    archivo. Las estrategias declaran símbolos/temporalidades como metadata, pero correr
    un backtest requiere que el dato exista de verdad."""
    for entry in list_available_datasets(DATA_DIR):
        if entry["symbol"] == symbol and entry["timeframe"] == timeframe:
            return entry["dataset"]
    raise HTTPException(
        status_code=400,
        detail=f"no hay dataset disponible para {symbol} {timeframe}",
    )


def _run_and_persist_backtest(
    db: Session, strategy: SavedStrategy, symbol: str, timeframe: str, initial_equity: float
) -> StrategyBacktestRun:
    if symbol not in strategy.symbols:
        raise HTTPException(status_code=400, detail=f"'{symbol}' no está entre los mercados de la estrategia")
    if timeframe not in strategy.timeframes:
        raise HTTPException(status_code=400, detail=f"'{timeframe}' no está entre las temporalidades de la estrategia")

    dataset = _resolve_run_dataset(symbol, timeframe)
    dataset_path = resolve_dataset(dataset, DATA_DIR)
    strategy_cls = resolve_strategy(strategy.strategy_type)

    effective_config = StrategyConfig.model_validate({**strategy.config, "symbol": symbol, "timeframe": timeframe})
    result = run_backtest_result(strategy_cls, effective_config, dataset_path, initial_equity)
    weekly_equity = result.equity_curve.resample("W").last().dropna()

    run = StrategyBacktestRun(
        strategy_id=strategy.id,
        symbol=symbol,
        timeframe=timeframe,
        dataset=dataset,
        config_snapshot=effective_config.model_dump(),
        initial_equity=initial_equity,
        num_trades=len(result.trades),
        metrics=result.metrics,
        equity_curve=[{"timestamp": ts.isoformat(), "equity": float(value)} for ts, value in weekly_equity.items()],
        trades=[
            {
                "side": t.side.value,
                "entry_timestamp": t.entry_timestamp.isoformat(),
                "exit_timestamp": t.exit_timestamp.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "commission": t.commission,
                "pnl": t.pnl,
            }
            for t in result.trades
        ],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/catalog", response_model=list[str])
def catalog() -> list[str]:
    return list_strategies()


@router.get("/datasets", response_model=list[dict[str, str]])
def datasets() -> list[dict[str, str]]:
    return list_available_datasets(DATA_DIR)


@router.post("", response_model=StrategyDetailResponse)
def create_strategy(
    request: CreateStrategyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StrategyDetailResponse:
    try:
        get_strategy(request.strategy_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _validate_timeframes(request.timeframes)

    if request.config.symbol not in request.symbols:
        raise HTTPException(status_code=400, detail="config.symbol debe estar entre los mercados declarados")
    if request.config.timeframe not in request.timeframes:
        raise HTTPException(status_code=400, detail="config.timeframe debe estar entre las temporalidades declaradas")

    strategy = SavedStrategy(
        user_id=user.id,
        name=request.name,
        strategy_type=request.strategy_type,
        category=request.category,
        symbols=request.symbols,
        timeframes=request.timeframes,
        entry_conditions=request.entry_conditions,
        exit_conditions=request.exit_conditions,
        config=request.config.model_dump(),
        status="active",
        notes=request.notes,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)

    # Corre el primer backtest al toque (mismo espíritu que paper trading al crear una
    # sesión): si falla, no dejamos una estrategia guardada sin ningún resultado.
    try:
        _run_and_persist_backtest(db, strategy, request.config.symbol, request.config.timeframe, request.initial_equity)
    except HTTPException:
        db.delete(strategy)
        db.commit()
        raise
    except Exception as exc:
        db.delete(strategy)
        db.commit()
        raise HTTPException(status_code=400, detail=f"no se pudo correr el primer backtest: {exc}") from exc

    db.refresh(strategy)
    return StrategyDetailResponse(
        **_to_strategy_response(strategy).model_dump(),
        backtest_runs=[_to_run_summary(r) for r in strategy.backtest_runs],
    )


@router.get("", response_model=list[StrategyResponse])
def list_saved_strategies(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[StrategyResponse]:
    strategies = (
        db.query(SavedStrategy).filter(SavedStrategy.user_id == user.id).order_by(SavedStrategy.created_at.desc()).all()
    )
    return [_to_strategy_response(s) for s in strategies]


@router.get("/{strategy_id}", response_model=StrategyDetailResponse)
def strategy_detail(
    strategy_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StrategyDetailResponse:
    strategy = _get_owned_strategy(strategy_id, user, db)
    return StrategyDetailResponse(
        **_to_strategy_response(strategy).model_dump(),
        backtest_runs=[_to_run_summary(r) for r in strategy.backtest_runs],
    )


@router.patch("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(
    strategy_id: int,
    request: UpdateStrategyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyResponse:
    strategy = _get_owned_strategy(strategy_id, user, db)
    updates = request.model_dump(exclude_unset=True)

    if "timeframes" in updates:
        _validate_timeframes(updates["timeframes"])
    if "config" in updates:
        # Dump completo (no exclude_unset): config es un reemplazo entero del bloque
        # técnico, no un merge parcial — si se omitiera exclude_unset acá también, los
        # campos de StrategyConfig con default (risk_per_trade, indicators, ...) que el
        # cliente no mandó explícitamente se perderían del JSON guardado.
        updates["config"] = request.config.model_dump()

    for field, value in updates.items():
        setattr(strategy, field, value)

    db.commit()
    db.refresh(strategy)
    return _to_strategy_response(strategy)


@router.post("/{strategy_id}/backtests", response_model=BacktestRunDetail)
def run_backtest(
    strategy_id: int,
    request: RunBacktestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    strategy = _get_owned_strategy(strategy_id, user, db)
    run = _run_and_persist_backtest(db, strategy, request.symbol, request.timeframe, request.initial_equity)
    return BacktestRunDetail(**_to_run_summary(run).model_dump(), config_snapshot=run.config_snapshot, equity_curve=run.equity_curve, trades=run.trades)


@router.get("/{strategy_id}/backtests/{run_id}", response_model=BacktestRunDetail)
def backtest_run_detail(
    strategy_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    strategy = _get_owned_strategy(strategy_id, user, db)
    run = (
        db.query(StrategyBacktestRun)
        .filter(StrategyBacktestRun.id == run_id, StrategyBacktestRun.strategy_id == strategy.id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="corrida no encontrada")
    return BacktestRunDetail(**_to_run_summary(run).model_dump(), config_snapshot=run.config_snapshot, equity_curve=run.equity_curve, trades=run.trades)
