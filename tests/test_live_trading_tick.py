import tradingos.live_trading.tick as tick_module
from tradingos.auth.security import hash_password
from tradingos.db import crypto
from tradingos.db.models import (
    BrokerConnection,
    LiveOrder,
    LiveTrade,
    LiveTradingSession,
    SavedStrategy,
    User,
)
from tradingos.db.session import SessionLocal
from tradingos.strategies.ma_crossover import default_config


def _make_user(db, email: str, **overrides) -> User:
    user = User(email=email, hashed_password=hash_password("hunter22"), **overrides)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_connection(db, user: User, *, trading_enabled: bool = True) -> BrokerConnection:
    connection = BrokerConnection(
        user_id=user.id,
        exchange="binance",
        label="cuenta",
        api_key_encrypted=crypto.encrypt("k"),
        api_secret_encrypted=crypto.encrypt("s"),
        trading_enabled=trading_enabled,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def _make_strategy(db, user: User, *, symbol: str = "BTCUSDT") -> SavedStrategy:
    strategy = SavedStrategy(
        user_id=user.id,
        name="Test",
        strategy_type="ma_crossover",
        category="swing",
        symbols=[symbol],
        timeframes=["1h"],
        config=default_config(symbol=symbol).model_dump(),
        status="active",
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def _make_session(
    db,
    user,
    strategy,
    connection,
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    status: str = "active",
    current_position=None,
) -> LiveTradingSession:
    session = LiveTradingSession(
        user_id=user.id,
        strategy_id=strategy.id,
        broker_connection_id=connection.id,
        exchange=connection.exchange,
        strategy=strategy.strategy_type,
        symbol=symbol,
        timeframe=timeframe,
        config=strategy.config,
        status=status,
        current_position=current_position,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _mock_fill(monkeypatch, filled_quantity: float, avg_price: float):
    monkeypatch.setattr(
        "tradingos.api.routers.brokers.binance_place_market_order",
        lambda api_key, api_secret, symbol, side, amount_usdt: {
            "exchange_order_id": "1",
            "raw": {"status": "FILLED"},
            "filled_quantity": filled_quantity,
            "avg_price": avg_price,
        },
    )


def _mock_balance(monkeypatch, usdt_free: float):
    monkeypatch.setattr(
        "tradingos.api.routers.brokers.get_spot_balances",
        lambda api_key, api_secret: [{"asset": "USDT", "free": usdt_free, "locked": 0.0, "total": usdt_free}],
    )


def test_run_tick_opens_real_position_when_strategy_signals_entry(monkeypatch, synthetic_ohlcv):
    # Mismo truco que test_paper_trading_tick.py: truncar la serie sintética a un punto
    # donde el cruce de EMA ya generó una posición abierta (no cerrada todavía).
    truncated = synthetic_ohlcv.iloc[:44].reset_index(drop=True)
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: truncated)
    _mock_balance(monkeypatch, usdt_free=10_000.0)
    _mock_fill(monkeypatch, filled_quantity=0.05, avg_price=101.5)

    db = SessionLocal()
    try:
        user = _make_user(db, "open@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)

        tick_module.run_tick_for_session(db, session)

        assert session.current_position is not None
        assert session.current_position["side"] == "long"
        assert session.current_position["quantity"] == 0.05
        assert session.current_position["entry_price"] == 101.5
        assert session.last_tick_at is not None

        orders = db.query(LiveOrder).filter(LiveOrder.live_trading_session_id == session.id).all()
        assert len(orders) == 1
        assert orders[0].side == "buy"
        assert orders[0].status == "submitted"
    finally:
        db.close()


def test_run_tick_does_nothing_when_strategy_already_flat_in_window(monkeypatch, synthetic_ohlcv):
    # La serie completa (uptrend + downtrend) hace que ma_crossover entre y salga sola
    # dentro de la ventana: al primer tick nunca estuvimos "de verdad" adentro, así que
    # no hay que perseguir ese trade ya cerrado — solo importa el estado actual.
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)
    _mock_balance(monkeypatch, usdt_free=10_000.0)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("no debería intentar mandar ninguna orden")

    monkeypatch.setattr("tradingos.api.routers.brokers.binance_place_market_order", _fail_if_called)

    db = SessionLocal()
    try:
        user = _make_user(db, "flat@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)

        tick_module.run_tick_for_session(db, session)

        assert session.current_position is None
        assert db.query(LiveOrder).filter(LiveOrder.live_trading_session_id == session.id).count() == 0
    finally:
        db.close()


def test_run_tick_closes_real_position_once_engine_confirms_it_closed(monkeypatch, synthetic_ohlcv):
    truncated = synthetic_ohlcv.iloc[:44].reset_index(drop=True)
    _mock_balance(monkeypatch, usdt_free=10_000.0)
    _mock_fill(monkeypatch, filled_quantity=0.05, avg_price=101.5)
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: truncated)

    db = SessionLocal()
    try:
        user = _make_user(db, "close@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)

        tick_module.run_tick_for_session(db, session)
        assert session.current_position is not None
        opened_entry_timestamp = session.current_position["entry_timestamp"]

        # El tiempo pasa: ahora llegan más velas (el resto de la serie), donde el cruce
        # de EMA a la baja cierra esa misma posición.
        monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)
        _mock_fill(monkeypatch, filled_quantity=0.05, avg_price=95.0)

        tick_module.run_tick_for_session(db, session)

        assert session.current_position is None
        trades = db.query(LiveTrade).filter(LiveTrade.session_id == session.id).all()
        assert len(trades) == 1
        assert trades[0].quantity == 0.05

        orders = db.query(LiveOrder).filter(LiveOrder.live_trading_session_id == session.id).order_by(LiveOrder.id).all()
        assert [o.side for o in orders] == ["buy", "sell"]
        assert opened_entry_timestamp is not None
    finally:
        db.close()


def test_run_tick_leaves_position_untouched_if_outside_lookback_window(monkeypatch, synthetic_ohlcv):
    # Simula una posición "vieja" cuyo entry_timestamp no aparece ni como trade cerrado
    # ni como posición final en el replay de esta ventana — limitación conocida
    # documentada en tick.py: no se toca, ni se cierra ni se abre una nueva encima.
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)
    _mock_balance(monkeypatch, usdt_free=10_000.0)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("no debería intentar mandar ninguna orden")

    monkeypatch.setattr("tradingos.api.routers.brokers.binance_place_market_order", _fail_if_called)

    db = SessionLocal()
    try:
        user = _make_user(db, "outside@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        fake_old_position = {
            "side": "long",
            "entry_price": 50.0,
            "quantity": 1.0,
            "stop_loss": None,
            "take_profit": None,
            "entry_timestamp": "2000-01-01T00:00:00+00:00",
            "opened_at": "2000-01-01T00:00:00+00:00",
        }
        session = _make_session(db, user, strategy, connection, current_position=fake_old_position)

        tick_module.run_tick_for_session(db, session)

        assert session.current_position == fake_old_position
        assert db.query(LiveOrder).filter(LiveOrder.live_trading_session_id == session.id).count() == 0
    finally:
        db.close()


def test_run_tick_rejected_order_does_not_change_position(monkeypatch, synthetic_ohlcv):
    from tradingos.connectors.binance import BinanceAPIError

    truncated = synthetic_ohlcv.iloc[:44].reset_index(drop=True)
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: truncated)
    _mock_balance(monkeypatch, usdt_free=10_000.0)

    def _raise(*args, **kwargs):
        raise BinanceAPIError("saldo insuficiente")

    monkeypatch.setattr("tradingos.api.routers.brokers.binance_place_market_order", _raise)

    db = SessionLocal()
    try:
        user = _make_user(db, "rejected@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)

        tick_module.run_tick_for_session(db, session)

        assert session.current_position is None
        orders = db.query(LiveOrder).filter(LiveOrder.live_trading_session_id == session.id).all()
        assert len(orders) == 1
        assert orders[0].status == "rejected"
        assert "saldo insuficiente" in orders[0].error_message
    finally:
        db.close()


def test_run_all_active_only_processes_active_sessions(monkeypatch, synthetic_ohlcv):
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)
    _mock_balance(monkeypatch, usdt_free=10_000.0)

    db = SessionLocal()
    try:
        user = _make_user(db, "activeonly@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        active = _make_session(db, user, strategy, connection, status="active")
        stopped = _make_session(db, user, strategy, connection, status="stopped")

        processed = tick_module.run_all_active(db)

        assert processed == 1
        db.refresh(active)
        db.refresh(stopped)
        assert active.last_tick_at is not None
        assert stopped.last_tick_at is None
    finally:
        db.close()


def test_run_all_active_pauses_sessions_of_a_user_that_breached_its_loss_limit(monkeypatch, synthetic_ohlcv):
    from datetime import datetime, timedelta, timezone as tz

    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)
    _mock_balance(monkeypatch, usdt_free=10_000.0)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("un usuario en breach no debería mandar ninguna orden en esta corrida")

    db = SessionLocal()
    try:
        breaching_user = _make_user(db, "breaching@example.com", daily_loss_limit_usdt=50.0)
        breaching_connection = _make_connection(db, breaching_user)
        breaching_strategy = _make_strategy(db, breaching_user)
        breaching_session = _make_session(db, breaching_user, breaching_strategy, breaching_connection)
        db.add(
            LiveTrade(
                session_id=breaching_session.id,
                side="long",
                entry_timestamp=datetime.now(tz.utc) - timedelta(hours=2),
                exit_timestamp=datetime.now(tz.utc) - timedelta(hours=1),
                entry_price=100.0,
                exit_price=40.0,
                quantity=1.0,
                pnl=-60.0,
            )
        )
        db.commit()

        ok_user = _make_user(db, "ok@example.com")
        ok_connection = _make_connection(db, ok_user)
        ok_strategy = _make_strategy(db, ok_user)
        ok_session = _make_session(db, ok_user, ok_strategy, ok_connection)

        monkeypatch.setattr("tradingos.api.routers.brokers.binance_place_market_order", _fail_if_called)

        processed = tick_module.run_all_active(db)

        assert processed == 1  # solo la del usuario sin breach
        db.refresh(breaching_session)
        db.refresh(ok_session)
        assert breaching_session.status == "risk_paused"
        assert breaching_session.paused_reason is not None
        assert breaching_session.last_tick_at is None  # nunca se llegó a tickear
        assert ok_session.last_tick_at is not None
    finally:
        db.close()


def test_lookback_start_scales_wall_clock_window_with_timeframe():
    from datetime import datetime, timedelta, timezone as tz

    from tradingos.data.binance_downloader import INTERVAL_MS

    now = datetime.now(tz.utc)
    for timeframe in ("1m", "15m", "1h", "1d"):
        start = tick_module._lookback_start(timeframe)
        expected = timedelta(milliseconds=INTERVAL_MS[timeframe] * tick_module.LOOKBACK_BARS * 1.2)
        actual = now - start
        assert abs((actual - expected).total_seconds()) < 5


def test_run_tick_works_for_non_1h_timeframe(monkeypatch, synthetic_ohlcv):
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)
    _mock_balance(monkeypatch, usdt_free=10_000.0)

    db = SessionLocal()
    try:
        user = _make_user(db, "tf4h@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection, timeframe="4h")

        tick_module.run_tick_for_session(db, session)

        assert session.last_tick_at is not None
    finally:
        db.close()
