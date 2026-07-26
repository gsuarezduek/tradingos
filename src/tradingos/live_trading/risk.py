from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from tradingos.db.models import LiveTrade, LiveTradingSession, User


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
