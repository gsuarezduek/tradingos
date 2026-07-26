from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.api.routers.brokers import EXCHANGE_API_ERRORS, ExchangeSpec, get_exchange_spec
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.risk import initial_stop_loss, initial_take_profit, position_size
from tradingos.core.strategy import StrategyConfig, get_strategy
from tradingos.core.types import Side
from tradingos.data.binance_downloader import fetch_klines
from tradingos.db import crypto
from tradingos.db.models import LiveOrder, LiveTrade, LiveTradingSession

# Mismo motor y misma ventana que paper_trading/tick.py — ver ese módulo para el porqué
# de LOOKBACK_BARS y su límite conocido (una posición abierta más tiempo que la ventana
# "sale de cuadro"). Acá ese límite es más delicado: si pasa, este tick simplemente deja
# de tocar esa posición (ni la cierra ni abre una nueva) en vez de arriesgar una acción
# equivocada con plata real — ver el bloque "posición no verificable" más abajo.
LOOKBACK_BARS = 1500

# initial_equity acá es solo un valor de referencia para que el motor pueda simular
# (no se usa para dimensionar la orden real, que se calcula aparte contra el saldo
# verdadero de la cuenta en _submit_open): la identidad de una posición (si abre/cierra)
# no depende de la magnitud del equity simulado.
_REFERENCE_EQUITY = 10_000.0


def _decrypt_credentials(session: LiveTradingSession) -> tuple[str, str, str | None]:
    connection = session.broker_connection
    api_key = crypto.decrypt(connection.api_key_encrypted)
    api_secret = crypto.decrypt(connection.api_secret_encrypted)
    passphrase = crypto.decrypt(connection.passphrase_encrypted) if connection.passphrase_encrypted else None
    return api_key, api_secret, passphrase


def _fetch_usdt_free_balance(spec: ExchangeSpec, api_key: str, api_secret: str, passphrase: str | None) -> float:
    try:
        balances = spec.spot_fn(api_key, api_secret, passphrase)
    except EXCHANGE_API_ERRORS:
        return 0.0
    for b in balances:
        if b["asset"] == "USDT":
            return float(b["free"])
    return 0.0


def _submit_order(
    db: Session,
    session: LiveTradingSession,
    spec: ExchangeSpec,
    api_key: str,
    api_secret: str,
    passphrase: str | None,
    side: str,
    amount_usdt: float,
) -> LiveOrder:
    order = LiveOrder(
        user_id=session.user_id,
        broker_connection_id=session.broker_connection_id,
        live_trading_session_id=session.id,
        exchange=session.exchange,
        symbol=session.symbol,
        side=side,
        amount_usdt=amount_usdt,
    )
    try:
        result = spec.order_fn(api_key, api_secret, passphrase, session.symbol, side, amount_usdt)
    except EXCHANGE_API_ERRORS as exc:
        order.status = "rejected"
        order.error_message = str(exc)
    else:
        order.status = "submitted"
        order.exchange_order_id = result.get("exchange_order_id")
        order.raw_response = result.get("raw")
        order.filled_quantity = result.get("filled_quantity")
        order.avg_price = result.get("avg_price")

    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _submit_open(
    db: Session,
    session: LiveTradingSession,
    spec: ExchangeSpec,
    api_key: str,
    api_secret: str,
    passphrase: str | None,
    price_ref: float,
    entry_timestamp_identity: str,
    config: StrategyConfig,
) -> None:
    side = Side.LONG  # ambas estrategias registradas son long-only por ahora
    stop = initial_stop_loss(price_ref, side, config)
    take_profit = initial_take_profit(price_ref, side, config)
    equity = _fetch_usdt_free_balance(spec, api_key, api_secret, passphrase)
    qty = position_size(equity, price_ref, stop if stop is not None else price_ref, config)
    amount_usdt = qty * price_ref
    if amount_usdt <= 0:
        # Sin saldo (o riesgo configurado en 0): no hay nada que mandar. Se reintenta
        # solo, el próximo tick, sin necesidad de ninguna acción especial acá.
        return

    order = _submit_order(db, session, spec, api_key, api_secret, passphrase, "buy", amount_usdt)
    if order.status != "submitted":
        return  # rechazada: current_position sigue None, se reintenta el próximo tick

    filled_qty = order.filled_quantity or qty
    fill_price = order.avg_price or price_ref
    session.current_position = {
        "side": side.value,
        "entry_price": fill_price,
        "quantity": filled_qty,
        "stop_loss": initial_stop_loss(fill_price, side, config),
        "take_profit": initial_take_profit(fill_price, side, config),
        "entry_timestamp": entry_timestamp_identity,
        "opened_at": datetime.now(timezone.utc).isoformat(),
    }


def _submit_close(
    db: Session,
    session: LiveTradingSession,
    spec: ExchangeSpec,
    api_key: str,
    api_secret: str,
    passphrase: str | None,
    price_ref: float,
) -> None:
    current = session.current_position
    assert current is not None
    amount_usdt = current["quantity"] * price_ref
    if amount_usdt <= 0:
        session.current_position = None
        return

    order = _submit_order(db, session, spec, api_key, api_secret, passphrase, "sell", amount_usdt)
    if order.status != "submitted":
        return  # rechazada: seguimos "abiertos" para nosotros, se reintenta el próximo tick

    exit_qty = order.filled_quantity or current["quantity"]
    exit_price = order.avg_price or price_ref
    direction = 1 if current["side"] == Side.LONG.value else -1
    pnl = (exit_price - current["entry_price"]) * exit_qty * direction

    db.add(
        LiveTrade(
            session_id=session.id,
            side=current["side"],
            entry_timestamp=datetime.fromisoformat(current["opened_at"]),
            exit_timestamp=datetime.now(timezone.utc),
            entry_price=current["entry_price"],
            exit_price=exit_price,
            quantity=exit_qty,
            pnl=pnl,
        )
    )
    session.current_position = None


def run_tick_for_session(db: Session, session: LiveTradingSession) -> None:
    """Reconcilia una LiveTradingSession contra el mercado real.

    A diferencia de paper trading, acá no alcanza con "recalcular todo de nuevo": una
    orden real ya mandada es irreversible. Este tick resuelve eso re-corriendo el mismo
    motor de backtest (determinístico) sobre la misma ventana de velas que usaría paper
    trading, y comparando lo que el replay dice que debería estar abierto AHORA
    (`result.final_position`) contra `session.current_position` (lo que de verdad
    tenemos abierto, según nuestras propias órdenes ya ejecutadas). Solo actúa sobre la
    diferencia: identifica una posición por su `entry_timestamp` de barra simulada.

    Limitación conocida (igual espíritu que LOOKBACK_BARS en paper_trading/tick.py): si
    `current_position` no aparece ni como trade cerrado ni como posición final dentro de
    la ventana de este replay (quedó "afuera" por ser más vieja que LOOKBACK_BARS), este
    tick no la toca — ni la cierra ni abre una nueva encima. Preferimos no actuar antes
    que arriesgar una decisión equivocada con plata real.
    """
    strategy_cls = get_strategy(session.strategy)
    config = StrategyConfig.model_validate(session.config)

    start = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_BARS * 1.2)
    data = fetch_klines(session.symbol, session.timeframe, start).tail(LOOKBACK_BARS).reset_index(drop=True)

    strategy = strategy_cls(config)
    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=_REFERENCE_EQUITY)
    result = engine.run(data)

    spec = get_exchange_spec(session.exchange)
    if spec is None:
        raise ValueError(f"exchange no soportado: {session.exchange}")
    api_key, api_secret, passphrase = _decrypt_credentials(session)
    price_ref = float(data.iloc[-1]["close"])

    closed_identities = {t.entry_timestamp.isoformat() for t in result.trades}
    final_identity = result.final_position.entry_timestamp.isoformat() if result.final_position else None

    current = session.current_position
    if current is not None:
        current_identity = current["entry_timestamp"]
        if current_identity == final_identity:
            # Sigue abierta: solo refrescamos SL/TP/trailing informativos con lo último
            # que calculó el replay (no dispara ninguna orden, es solo para mostrar).
            session.current_position = {
                **current,
                "stop_loss": result.final_position.stop_loss,
                "take_profit": result.final_position.take_profit,
            }
        elif current_identity in closed_identities:
            _submit_close(db, session, spec, api_key, api_secret, passphrase, price_ref)
            current = session.current_position  # None si se cerró bien
        # si no está en ninguna de las dos: ver limitación conocida en el docstring — no se toca.

    if result.final_position is not None and session.current_position is None:
        _submit_open(db, session, spec, api_key, api_secret, passphrase, price_ref, final_identity, config)

    session.last_tick_at = datetime.now(timezone.utc)
    db.commit()


def run_all_active(db: Session) -> int:
    """Corre el tick de todas las LiveTradingSession activas. Una sesión que falla
    (símbolo inválido, exchange caído, etc.) no aborta el resto del batch."""
    sessions = db.query(LiveTradingSession).filter(LiveTradingSession.status == "active").all()
    processed = 0
    for session in sessions:
        try:
            run_tick_for_session(db, session)
            processed += 1
        except Exception as exc:  # noqa: BLE001 — una sesión rota no debe tumbar el resto del batch
            db.rollback()
            print(f"trading en vivo: tick de la sesión {session.id} falló: {exc}", file=sys.stderr)
    return processed
