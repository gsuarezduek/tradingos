from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from tradingos.db.models import LiveTrade, LiveTradingSession, User

# Estados de LiveTradingSession cuya current_position cuenta como exposición real
# todavía abierta. "risk_paused" es una pausa que decide el propio sistema (sigue
# siendo su responsabilidad, ver pause_active_sessions_for_risk); "stopped" es una
# decisión explícita del usuario y, como documenta stop_session, a partir de ahí
# gestionar esa posición "le corresponde a él, no al sistema" — se excluye a propósito
# aunque pueda seguir habiendo una posición real abierta en el exchange.
_EXPOSURE_COUNTING_STATUSES = ("active", "risk_paused")


@dataclass
class LossLimitBreach:
    window: str  # "diaria" | "semanal"
    limit_usdt: float
    realized_pnl_usdt: float

    def reason(self) -> str:
        return (
            f"límite de pérdida {self.window} alcanzado: ${self.realized_pnl_usdt:.2f} "
            f"(límite: -${self.limit_usdt:.2f})"
        )


def _realized_pnl_since(db: Session, user: User, since: datetime) -> float:
    total = (
        db.query(func.sum(LiveTrade.pnl))
        .join(LiveTradingSession, LiveTrade.session_id == LiveTradingSession.id)
        .filter(LiveTradingSession.user_id == user.id, LiveTrade.exit_timestamp >= since)
        .scalar()
    )
    return total or 0.0


def check_loss_limits(db: Session, user: User) -> LossLimitBreach | None:
    """Evalúa la pérdida realizada agregada del usuario (todas sus LiveTradingSession
    juntas) contra sus límites configurados, en ventanas rolling (no de calendario) para
    no dejar pasar una racha repartida justo alrededor de la medianoche UTC."""
    now = datetime.now(timezone.utc)

    if user.daily_loss_limit_usdt is not None:
        pnl = _realized_pnl_since(db, user, now - timedelta(days=1))
        if pnl <= -user.daily_loss_limit_usdt:
            return LossLimitBreach("diaria", user.daily_loss_limit_usdt, pnl)

    if user.weekly_loss_limit_usdt is not None:
        pnl = _realized_pnl_since(db, user, now - timedelta(days=7))
        if pnl <= -user.weekly_loss_limit_usdt:
            return LossLimitBreach("semanal", user.weekly_loss_limit_usdt, pnl)

    return None


def pause_active_sessions_for_risk(db: Session, user: User, breach: LossLimitBreach) -> int:
    """Pausa (no cierra posiciones) todas las sesiones activas del usuario. A diferencia
    de detener a mano, queda status='risk_paused' con el motivo visible en paused_reason
    — no hay auto-resume, el usuario tiene que revisar y crear una sesión nueva."""
    sessions = (
        db.query(LiveTradingSession)
        .filter(LiveTradingSession.user_id == user.id, LiveTradingSession.status == "active")
        .all()
    )
    reason = breach.reason()
    for session in sessions:
        session.status = "risk_paused"
        session.paused_reason = reason
    db.commit()
    return len(sessions)


def open_exposure_usdt(
    db: Session, user: User, *, symbol: str | None = None, strategy_id: int | None = None
) -> float:
    """Suma la exposición abierta (quantity * entry_price al momento de abrir) de las
    LiveTradingSession del usuario cuyo status cuenta como exposición real (ver
    _EXPOSURE_COUNTING_STATUSES) y que tienen una posición abierta ahora mismo.

    `symbol` y `strategy_id` son filtros independientes (no una intersección): pasar
    solo uno agrega a través de todas las estrategias/símbolos, no ambos a la vez.
    Se suma en Python, no en SQL, porque current_position es JSON y no hay precedente
    de filtrarlo a nivel de base de datos (ver live_trading/tick.py).

    Solo ve lo que el propio sistema abrió — igual que check_loss_limits solo ve
    LiveTrade.pnl de trades que el sistema ejecutó — así que no detecta exposición de
    operaciones manuales hechas directamente en el exchange, fuera de la plataforma.
    """
    query = db.query(LiveTradingSession).filter(
        LiveTradingSession.user_id == user.id,
        LiveTradingSession.status.in_(_EXPOSURE_COUNTING_STATUSES),
    )
    if symbol is not None:
        query = query.filter(LiveTradingSession.symbol == symbol)
    if strategy_id is not None:
        query = query.filter(LiveTradingSession.strategy_id == strategy_id)

    total = 0.0
    for session in query.all():
        position = session.current_position
        if position is not None:
            total += position["quantity"] * position["entry_price"]
    return total


def exposure_capped_amount_usdt(
    db: Session, user: User, session: LiveTradingSession, amount_usdt: float
) -> float:
    """Clampea el monto de una orden de apertura nueva al headroom que le queda al
    usuario bajo sus topes de exposición configurados (por activo y por estrategia,
    tomando el más chico de los dos si ambos están configurados). Sin límites
    configurados devuelve amount_usdt sin tocar. El headroom nunca es negativo: si ya
    se superó el tope (por ejemplo, bajando el límite después de tener posiciones
    abiertas), esta función devuelve 0.0 en vez de un número negativo.
    """
    headrooms = []
    if user.max_exposure_per_asset_usdt is not None:
        used = open_exposure_usdt(db, user, symbol=session.symbol)
        headrooms.append(max(0.0, user.max_exposure_per_asset_usdt - used))
    if user.max_exposure_per_strategy_usdt is not None:
        used = open_exposure_usdt(db, user, strategy_id=session.strategy_id)
        headrooms.append(max(0.0, user.max_exposure_per_strategy_usdt - used))

    if not headrooms:
        return amount_usdt
    return min(amount_usdt, *headrooms)
