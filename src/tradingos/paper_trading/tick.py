from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import StrategyConfig, get_strategy
from tradingos.data.binance_downloader import fetch_klines
from tradingos.db.models import PaperTrade, PaperTradingSession

# Cada tick re-corre el motor completo sobre una ventana acotada en vez de mantener
# estado incremental barra a barra: es más simple y, a este tamaño, rápido (40k velas ya
# miden ~8s en producción; esto es una fracción). Límite conocido: una posición abierta
# por más tiempo que la ventana "se pierde" al re-correr — riesgo bajo para una
# estrategia de cruce de medias, aceptado como simplificación de v1.
LOOKBACK_BARS = 1500
_EQUITY_CURVE_POINTS = 200


def run_tick_for_session(db: Session, session: PaperTradingSession) -> None:
    strategy_cls = get_strategy(session.strategy)
    config = StrategyConfig.model_validate(session.config)

    # Margen generoso sobre LOOKBACK_BARS horas: de sobra para timeframes >= 1h.
    start = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_BARS * 1.2)
    data = fetch_klines(session.symbol, session.timeframe, start).tail(LOOKBACK_BARS).reset_index(drop=True)

    strategy = strategy_cls(config)
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=session.initial_equity)
    result = engine.run(data)

    session.current_equity = float(result.equity_curve.iloc[-1]) if len(result.equity_curve) else session.initial_equity
    session.equity_curve = [
        {"timestamp": ts.isoformat(), "equity": float(value)} for ts, value in result.equity_curve.tail(_EQUITY_CURVE_POINTS).items()
    ]
    session.open_position = (
        {
            "side": result.final_position.side.value,
            "entry_price": result.final_position.entry_price,
            "quantity": result.final_position.quantity,
            "stop_loss": result.final_position.stop_loss,
            "take_profit": result.final_position.take_profit,
            "entry_timestamp": result.final_position.entry_timestamp.isoformat() if result.final_position.entry_timestamp else None,
        }
        if result.final_position is not None
        else None
    )
    session.last_tick_at = datetime.now(timezone.utc)

    # La ventana es determinística: se reemplazan los trades en vez de tratar de
    # deduplicar contra lo que ya había.
    db.query(PaperTrade).filter(PaperTrade.session_id == session.id).delete()
    for trade in result.trades:
        db.add(
            PaperTrade(
                session_id=session.id,
                side=trade.side.value,
                entry_timestamp=trade.entry_timestamp,
                exit_timestamp=trade.exit_timestamp,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                commission=trade.commission,
                pnl=trade.pnl,
            )
        )
    db.commit()


def run_all_active(db: Session) -> int:
    """Corre el tick de todas las sesiones activas. Una sesión que falla (ej. símbolo
    inválido, Binance no responde) no aborta el resto del batch."""
    sessions = db.query(PaperTradingSession).filter(PaperTradingSession.status == "active").all()
    processed = 0
    for session in sessions:
        try:
            run_tick_for_session(db, session)
            processed += 1
        except Exception as exc:  # noqa: BLE001 — un símbolo roto no debe tumbar el resto del batch
            db.rollback()
            print(f"paper trading: tick de la sesión {session.id} falló: {exc}", file=sys.stderr)
    return processed
