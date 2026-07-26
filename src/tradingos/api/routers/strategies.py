from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from tradingos.auth.dependencies import get_current_user
from tradingos.backtest.engine import SUPPORTED_TIMEFRAMES
from tradingos.backtest.service import DATA_DIR, list_available_datasets, resolve_dataset, resolve_strategy, run_backtest_result
from tradingos.core.conditions import CONDITION_CATALOG, Condition, describe_conditions, validate_condition
from tradingos.core.strategy import StrategyConfig, get_strategy, list_strategies
from tradingos.db.models import LiveTradingSession, PaperTradingSession, SavedStrategy, StrategyBacktestRun, User
from tradingos.db.session import get_db

router = APIRouter(prefix="/strategies", tags=["strategies"])

Category = Literal["scalping", "day_trading", "swing"]
Status = Literal["active", "paused"]


def _validate_rules(conditions: list[Condition]) -> None:
    for condition in conditions:
        try:
            validate_condition(condition)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


class CreateStrategyRequest(BaseModel):
    name: str
    strategy_type: str = "ma_crossover"
    category: Category
    symbols: list[str] = Field(min_length=1)
    timeframes: list[str] = Field(min_length=1)
    # entry_conditions/exit_conditions ya no los manda el cliente: se autogeneran (ver
    # describe_conditions) a partir de entry_rules/exit_rules, el constructor de
    # condiciones. entry_rules es obligatorio (>=1) para strategy_type="condition_based";
    # ma_crossover no los usa (los ignora StrategyConfig).
    entry_rules: list[Condition] = Field(default_factory=list)
    exit_rules: list[Condition] = Field(default_factory=list)
    config: StrategyConfig
    notes: str = ""
    initial_equity: float = 10_000.0

    @model_validator(mode="after")
    def _condition_based_needs_entry_rules(self) -> "CreateStrategyRequest":
        if self.strategy_type == "condition_based" and not self.entry_rules:
            raise ValueError("una estrategia por condiciones necesita al menos una condición de entrada")
        return self


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    category: Category | None = None
    symbols: list[str] | None = Field(default=None, min_length=1)
    timeframes: list[str] | None = Field(default=None, min_length=1)
    entry_rules: list[Condition] | None = None
    exit_rules: list[Condition] | None = None
    config: StrategyConfig | None = None
    status: Status | None = None
    notes: str | None = None


class RunBacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    initial_equity: float = 10_000.0
    # None = todo el histórico disponible del dataset. Formato "YYYY-MM-DD" o ISO 8601.
    start_date: str | None = None
    end_date: str | None = None


class BacktestRunSummary(BaseModel):
    id: int
    symbol: str
    timeframe: str
    dataset: str
    initial_equity: float
    range_start: str | None
    range_end: str | None
    num_trades: int
    metrics: dict[str, Any]
    total_pnl: float
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
    # Texto autogenerado (ver describe_conditions) a partir de entry_rules/exit_rules.
    entry_conditions: str
    exit_conditions: str
    entry_rules: list[dict[str, Any]]
    exit_rules: list[dict[str, Any]]
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
        entry_rules=strategy.entry_rules,
        exit_rules=strategy.exit_rules,
        config=strategy.config,
        status=strategy.status,
        notes=strategy.notes,
        created_at=strategy.created_at.isoformat(),
        updated_at=strategy.updated_at.isoformat(),
        latest_run=_to_run_summary(latest_run) if latest_run else None,
    )


def _to_run_summary(run: StrategyBacktestRun) -> BacktestRunSummary:
    # El equity_curve guardado es un resampleo semanal (ver run_backtest_summary), pero
    # su último punto siempre incluye el último valor real de la serie completa — así
    # que restar contra initial_equity da el PnL total exacto sin guardar una columna aparte.
    final_equity = run.equity_curve[-1]["equity"] if run.equity_curve else run.initial_equity
    return BacktestRunSummary(
        id=run.id,
        symbol=run.symbol,
        timeframe=run.timeframe,
        dataset=run.dataset,
        initial_equity=run.initial_equity,
        range_start=run.range_start.isoformat() if run.range_start else None,
        range_end=run.range_end.isoformat() if run.range_end else None,
        num_trades=run.num_trades,
        metrics=run.metrics,
        total_pnl=final_equity - run.initial_equity,
        created_at=run.created_at.isoformat(),
    )


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"fecha inválida: '{value}' (usar formato YYYY-MM-DD)") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


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
    db: Session,
    strategy: SavedStrategy,
    symbol: str,
    timeframe: str,
    initial_equity: float,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> StrategyBacktestRun:
    if symbol not in strategy.symbols:
        raise HTTPException(status_code=400, detail=f"'{symbol}' no está entre los mercados de la estrategia")
    if timeframe not in strategy.timeframes:
        raise HTTPException(status_code=400, detail=f"'{timeframe}' no está entre las temporalidades de la estrategia")
    if range_start is not None and range_end is not None and range_start >= range_end:
        raise HTTPException(status_code=400, detail="la fecha de inicio debe ser anterior a la fecha de fin")

    dataset = _resolve_run_dataset(symbol, timeframe)
    dataset_path = resolve_dataset(dataset, DATA_DIR)
    strategy_cls = resolve_strategy(strategy.strategy_type)

    effective_config = StrategyConfig.model_validate(
        {
            **strategy.config,
            "symbol": symbol,
            "timeframe": timeframe,
            "entry_rules": strategy.entry_rules,
            "exit_rules": strategy.exit_rules,
        }
    )
    result = run_backtest_result(strategy_cls, effective_config, dataset_path, initial_equity, range_start, range_end)
    weekly_equity = result.equity_curve.resample("W").last().dropna()

    run = StrategyBacktestRun(
        strategy_id=strategy.id,
        symbol=symbol,
        timeframe=timeframe,
        dataset=dataset,
        config_snapshot=effective_config.model_dump(),
        initial_equity=initial_equity,
        range_start=range_start,
        range_end=range_end,
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


@router.get("/conditions/catalog", response_model=list[dict[str, Any]])
def conditions_catalog() -> list[dict[str, Any]]:
    """Catálogo completo del constructor de condiciones (todas las categorías, cada una
    con `available`). Público: es metadata de UI, no depende del usuario."""
    return CONDITION_CATALOG


@router.post("", response_model=StrategyDetailResponse)
def create_strategy(
    request: CreateStrategyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StrategyDetailResponse:
    try:
        get_strategy(request.strategy_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _validate_timeframes(request.timeframes)
    _validate_rules(request.entry_rules)
    _validate_rules(request.exit_rules)

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
        entry_conditions=describe_conditions(request.entry_rules),
        exit_conditions=describe_conditions(request.exit_rules),
        entry_rules=[c.model_dump() for c in request.entry_rules],
        exit_rules=[c.model_dump() for c in request.exit_rules],
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
    if "entry_rules" in updates:
        assert request.entry_rules is not None
        _validate_rules(request.entry_rules)
        if strategy.strategy_type == "condition_based" and not request.entry_rules:
            raise HTTPException(
                status_code=400, detail="una estrategia por condiciones necesita al menos una condición de entrada"
            )
        updates["entry_rules"] = [c.model_dump() for c in request.entry_rules]
        updates["entry_conditions"] = describe_conditions(request.entry_rules)
    if "exit_rules" in updates:
        assert request.exit_rules is not None
        _validate_rules(request.exit_rules)
        updates["exit_rules"] = [c.model_dump() for c in request.exit_rules]
        updates["exit_conditions"] = describe_conditions(request.exit_rules)
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


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(
    strategy_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    strategy = _get_owned_strategy(strategy_id, user, db)

    # Trading Automático (plata real) no tiene forma de desvincularse de su estrategia
    # (LiveTradingSession.strategy_id no es nullable): si borráramos la estrategia se
    # rompería la integridad de ese historial. Paper trading sí es nullable — se
    # desvincula para conservar su historial sin la estrategia.
    has_live_sessions = (
        db.query(LiveTradingSession).filter(LiveTradingSession.strategy_id == strategy.id).first() is not None
    )
    if has_live_sessions:
        raise HTTPException(
            status_code=400,
            detail="no se puede eliminar: tiene sesiones de Trading Automático asociadas",
        )

    db.query(PaperTradingSession).filter(PaperTradingSession.strategy_id == strategy.id).update(
        {"strategy_id": None}
    )
    db.delete(strategy)
    db.commit()
    return Response(status_code=204)


@router.post("/{strategy_id}/backtests", response_model=BacktestRunDetail)
def run_backtest(
    strategy_id: int,
    request: RunBacktestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    strategy = _get_owned_strategy(strategy_id, user, db)
    range_start = _parse_date(request.start_date)
    range_end = _parse_date(request.end_date)
    run = _run_and_persist_backtest(
        db, strategy, request.symbol, request.timeframe, request.initial_equity, range_start, range_end
    )
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


@router.delete("/{strategy_id}/backtests/{run_id}", status_code=204)
def delete_backtest_run(
    strategy_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    strategy = _get_owned_strategy(strategy_id, user, db)
    run = (
        db.query(StrategyBacktestRun)
        .filter(StrategyBacktestRun.id == run_id, StrategyBacktestRun.strategy_id == strategy.id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="corrida no encontrada")
    db.delete(run)
    db.commit()
    return Response(status_code=204)
