from datetime import datetime, timedelta, timezone

from tradingos.auth.security import hash_password
from tradingos.db import crypto
from tradingos.db.models import BrokerConnection, LiveTrade, LiveTradingSession, SavedStrategy, User
from tradingos.db.session import SessionLocal
from tradingos.live_trading.risk import (
    check_loss_limits,
    exposure_capped_amount_usdt,
    open_exposure_usdt,
    pause_active_sessions_for_risk,
)
from tradingos.strategies.ma_crossover import default_config


def _make_user(db, email: str, **overrides) -> User:
    user = User(email=email, hashed_password=hash_password("hunter22"), **overrides)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_connection(db, user: User) -> BrokerConnection:
    connection = BrokerConnection(
        user_id=user.id,
        exchange="binance",
        label="cuenta",
        api_key_encrypted=crypto.encrypt("k"),
        api_secret_encrypted=crypto.encrypt("s"),
        trading_enabled=True,
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
    db, user, strategy, connection, *, symbol: str = "BTCUSDT", status: str = "active", current_position=None
) -> LiveTradingSession:
    session = LiveTradingSession(
        user_id=user.id,
        strategy_id=strategy.id,
        broker_connection_id=connection.id,
        exchange=connection.exchange,
        strategy=strategy.strategy_type,
        symbol=symbol,
        timeframe="1h",
        config=strategy.config,
        status=status,
        current_position=current_position,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _position(*, quantity: float, entry_price: float) -> dict:
    return {
        "side": "long",
        "entry_price": entry_price,
        "quantity": quantity,
        "stop_loss": None,
        "take_profit": None,
        "entry_timestamp": "2024-01-01T00:00:00+00:00",
        "opened_at": "2024-01-01T00:00:00+00:00",
    }


def _make_trade(db, session: LiveTradingSession, *, pnl: float, exit_timestamp: datetime) -> LiveTrade:
    trade = LiveTrade(
        session_id=session.id,
        side="long",
        entry_timestamp=exit_timestamp - timedelta(hours=1),
        exit_timestamp=exit_timestamp,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
    )
    db.add(trade)
    db.commit()
    return trade


def test_check_loss_limits_returns_none_without_configured_limits():
    db = SessionLocal()
    try:
        user = _make_user(db, "nolimits@example.com")
        assert check_loss_limits(db, user) is None
    finally:
        db.close()


def test_check_loss_limits_detects_daily_breach(monkeypatch):
    db = SessionLocal()
    try:
        user = _make_user(db, "dailybreach@example.com", daily_loss_limit_usdt=50.0)
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)
        _make_trade(db, session, pnl=-60.0, exit_timestamp=datetime.now(timezone.utc) - timedelta(hours=2))

        breach = check_loss_limits(db, user)

        assert breach is not None
        assert breach.window == "diaria"
        assert breach.limit_usdt == 50.0
        assert breach.realized_pnl_usdt == -60.0
    finally:
        db.close()


def test_check_loss_limits_ignores_trades_outside_the_window():
    db = SessionLocal()
    try:
        user = _make_user(db, "outsidewindow@example.com", daily_loss_limit_usdt=50.0)
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)
        # pérdida grande, pero de hace 2 días: no cuenta para el límite diario (rolling 24h)
        _make_trade(db, session, pnl=-1000.0, exit_timestamp=datetime.now(timezone.utc) - timedelta(days=2))

        assert check_loss_limits(db, user) is None
    finally:
        db.close()


def test_check_loss_limits_falls_back_to_weekly_when_daily_ok():
    db = SessionLocal()
    try:
        user = _make_user(
            db, "weeklybreach@example.com", daily_loss_limit_usdt=1000.0, weekly_loss_limit_usdt=50.0
        )
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)
        # fuera de la ventana diaria (24h) pero dentro de la semanal (7d)
        _make_trade(db, session, pnl=-60.0, exit_timestamp=datetime.now(timezone.utc) - timedelta(days=3))

        breach = check_loss_limits(db, user)

        assert breach is not None
        assert breach.window == "semanal"
    finally:
        db.close()


def test_pause_active_sessions_for_risk_only_touches_the_breaching_user():
    db = SessionLocal()
    try:
        user_a = _make_user(db, "usera@example.com", daily_loss_limit_usdt=50.0)
        user_b = _make_user(db, "userb@example.com")
        connection_a = _make_connection(db, user_a)
        connection_b = _make_connection(db, user_b)
        strategy_a = _make_strategy(db, user_a)
        strategy_b = _make_strategy(db, user_b)
        session_a = _make_session(db, user_a, strategy_a, connection_a)
        stopped_a = _make_session(db, user_a, strategy_a, connection_a, status="stopped")
        session_b = _make_session(db, user_b, strategy_b, connection_b)
        _make_trade(db, session_a, pnl=-60.0, exit_timestamp=datetime.now(timezone.utc) - timedelta(hours=1))

        breach = check_loss_limits(db, user_a)
        assert breach is not None
        paused_count = pause_active_sessions_for_risk(db, user_a, breach)

        assert paused_count == 1
        db.refresh(session_a)
        db.refresh(stopped_a)
        db.refresh(session_b)
        assert session_a.status == "risk_paused"
        assert session_a.paused_reason is not None
        assert "diaria" in session_a.paused_reason
        assert stopped_a.status == "stopped"  # ya estaba detenida a mano, no se toca
        assert session_b.status == "active"  # otro usuario, no debe verse afectado
    finally:
        db.close()


def test_open_exposure_usdt_is_zero_without_open_positions():
    db = SessionLocal()
    try:
        user = _make_user(db, "noexposure@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(db, user, strategy, connection)

        assert open_exposure_usdt(db, user) == 0.0
    finally:
        db.close()


def test_open_exposure_usdt_sums_by_symbol_across_strategies():
    db = SessionLocal()
    try:
        user = _make_user(db, "bysymbol@example.com")
        connection = _make_connection(db, user)
        strategy_a = _make_strategy(db, user)
        strategy_b = _make_strategy(db, user)
        _make_session(
            db, user, strategy_a, connection, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=100.0)
        )
        _make_session(
            db, user, strategy_b, connection, symbol="BTCUSDT", current_position=_position(quantity=2.0, entry_price=50.0)
        )

        assert open_exposure_usdt(db, user, symbol="BTCUSDT") == 200.0
    finally:
        db.close()


def test_open_exposure_usdt_sums_by_strategy_across_symbols():
    db = SessionLocal()
    try:
        user = _make_user(db, "bystrategy@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(
            db, user, strategy, connection, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=100.0)
        )
        _make_session(
            db, user, strategy, connection, symbol="ETHUSDT", current_position=_position(quantity=2.0, entry_price=50.0)
        )

        assert open_exposure_usdt(db, user, strategy_id=strategy.id) == 200.0
        assert open_exposure_usdt(db, user, symbol="BTCUSDT") == 100.0  # el filtro por symbol no mezcla el otro par
    finally:
        db.close()


def test_open_exposure_usdt_ignores_other_users():
    db = SessionLocal()
    try:
        user_a = _make_user(db, "expa@example.com")
        user_b = _make_user(db, "expb@example.com")
        connection_a = _make_connection(db, user_a)
        connection_b = _make_connection(db, user_b)
        strategy_a = _make_strategy(db, user_a)
        strategy_b = _make_strategy(db, user_b)
        _make_session(
            db, user_a, strategy_a, connection_a, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=100.0)
        )
        _make_session(
            db, user_b, strategy_b, connection_b, symbol="BTCUSDT", current_position=_position(quantity=5.0, entry_price=100.0)
        )

        assert open_exposure_usdt(db, user_a, symbol="BTCUSDT") == 100.0
    finally:
        db.close()


def test_open_exposure_usdt_ignores_sessions_without_position():
    db = SessionLocal()
    try:
        user = _make_user(db, "flatexposure@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(db, user, strategy, connection, symbol="BTCUSDT", current_position=None)

        assert open_exposure_usdt(db, user, symbol="BTCUSDT") == 0.0
    finally:
        db.close()


def test_open_exposure_usdt_counts_risk_paused_but_not_stopped():
    db = SessionLocal()
    try:
        user = _make_user(db, "pausedexposure@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(
            db,
            user,
            strategy,
            connection,
            symbol="BTCUSDT",
            status="risk_paused",
            current_position=_position(quantity=1.0, entry_price=100.0),
        )
        _make_session(
            db,
            user,
            strategy,
            connection,
            symbol="BTCUSDT",
            status="stopped",
            current_position=_position(quantity=3.0, entry_price=100.0),
        )

        # solo cuenta la risk_paused (100.0) — la stopped quedó bajo responsabilidad del
        # usuario, no del sistema, aunque su current_position siga sin limpiarse.
        assert open_exposure_usdt(db, user, symbol="BTCUSDT") == 100.0
    finally:
        db.close()


def test_exposure_capped_amount_usdt_returns_unchanged_without_limits():
    db = SessionLocal()
    try:
        user = _make_user(db, "nocaps@example.com")
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        session = _make_session(db, user, strategy, connection)

        assert exposure_capped_amount_usdt(db, user, session, 500.0) == 500.0
    finally:
        db.close()


def test_exposure_capped_amount_usdt_caps_to_asset_headroom():
    db = SessionLocal()
    try:
        user = _make_user(db, "assetcap@example.com", max_exposure_per_asset_usdt=300.0)
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(
            db, user, strategy, connection, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=250.0)
        )
        new_session = _make_session(db, user, strategy, connection, symbol="BTCUSDT")

        # headroom = 300 - 250 = 50, más chico que el amount_usdt propuesto (200)
        assert exposure_capped_amount_usdt(db, user, new_session, 200.0) == 50.0
    finally:
        db.close()


def test_exposure_capped_amount_usdt_caps_to_strategy_headroom():
    db = SessionLocal()
    try:
        user = _make_user(db, "strategycap@example.com", max_exposure_per_strategy_usdt=300.0)
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(
            db, user, strategy, connection, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=250.0)
        )
        new_session = _make_session(db, user, strategy, connection, symbol="ETHUSDT")

        assert exposure_capped_amount_usdt(db, user, new_session, 200.0) == 50.0
    finally:
        db.close()


def test_exposure_capped_amount_usdt_uses_minimum_of_both_caps():
    db = SessionLocal()
    try:
        user = _make_user(
            db, "bothcaps@example.com", max_exposure_per_asset_usdt=280.0, max_exposure_per_strategy_usdt=230.0
        )
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(
            db, user, strategy, connection, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=200.0)
        )
        new_session = _make_session(db, user, strategy, connection, symbol="BTCUSDT")

        # headroom activo = 280 - 200 = 80; headroom estrategia = 230 - 200 = 30 -> gana el más chico
        assert exposure_capped_amount_usdt(db, user, new_session, 200.0) == 30.0
    finally:
        db.close()


def test_exposure_capped_amount_usdt_floors_negative_headroom_at_zero():
    db = SessionLocal()
    try:
        user = _make_user(db, "overcap@example.com", max_exposure_per_asset_usdt=100.0)
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        _make_session(
            db, user, strategy, connection, symbol="BTCUSDT", current_position=_position(quantity=1.0, entry_price=500.0)
        )
        new_session = _make_session(db, user, strategy, connection, symbol="BTCUSDT")

        assert exposure_capped_amount_usdt(db, user, new_session, 200.0) == 0.0
    finally:
        db.close()


def test_exposure_capped_amount_usdt_does_not_increase_amount_below_headroom():
    db = SessionLocal()
    try:
        user = _make_user(db, "smallamount@example.com", max_exposure_per_asset_usdt=1000.0)
        connection = _make_connection(db, user)
        strategy = _make_strategy(db, user)
        new_session = _make_session(db, user, strategy, connection, symbol="BTCUSDT")

        assert exposure_capped_amount_usdt(db, user, new_session, 10.0) == 10.0
    finally:
        db.close()
