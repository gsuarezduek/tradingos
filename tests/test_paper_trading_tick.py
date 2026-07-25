import tradingos.paper_trading.tick as tick_module
from tradingos.auth.security import hash_password
from tradingos.db.models import PaperTrade, PaperTradingSession, User
from tradingos.db.session import SessionLocal
from tradingos.strategies.ma_crossover import default_config


def _make_user(db, email: str) -> User:
    user = User(email=email, hashed_password=hash_password("hunter22"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_session(db, user: User, *, symbol: str = "BTCUSDT", status: str = "active") -> PaperTradingSession:
    config = default_config(symbol=symbol)
    session = PaperTradingSession(
        user_id=user.id,
        strategy="ma_crossover",
        symbol=config.symbol,
        timeframe=config.timeframe,
        config=config.model_dump(),
        initial_equity=10_000.0,
        current_equity=10_000.0,
        equity_curve=[],
        status=status,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_run_tick_for_session_persists_equity_curve_and_trades(monkeypatch, synthetic_ohlcv):
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)

    db = SessionLocal()
    try:
        user = _make_user(db, "tick@example.com")
        session = _make_session(db, user)

        tick_module.run_tick_for_session(db, session)

        assert session.last_tick_at is not None
        assert session.current_equity > 0
        assert len(session.equity_curve) > 0
        assert session.equity_curve[0]["timestamp"]

        trades = db.query(PaperTrade).filter(PaperTrade.session_id == session.id).all()
        assert len(trades) >= 1
    finally:
        db.close()


def test_run_tick_for_session_replaces_trades_on_rerun(monkeypatch, synthetic_ohlcv):
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)

    db = SessionLocal()
    try:
        user = _make_user(db, "rerun@example.com")
        session = _make_session(db, user)

        tick_module.run_tick_for_session(db, session)
        first_count = db.query(PaperTrade).filter(PaperTrade.session_id == session.id).count()

        tick_module.run_tick_for_session(db, session)
        second_count = db.query(PaperTrade).filter(PaperTrade.session_id == session.id).count()

        assert first_count == second_count  # misma ventana determinística -> mismos trades, no duplicados
    finally:
        db.close()


def test_run_tick_for_session_captures_open_position(monkeypatch, synthetic_ohlcv):
    truncated = synthetic_ohlcv.iloc[:44].reset_index(drop=True)
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: truncated)

    db = SessionLocal()
    try:
        user = _make_user(db, "openpos@example.com")
        session = _make_session(db, user)

        tick_module.run_tick_for_session(db, session)

        assert session.open_position is not None
        assert session.open_position["side"] == "long"
    finally:
        db.close()


def test_run_all_active_only_processes_active_sessions(monkeypatch, synthetic_ohlcv):
    monkeypatch.setattr(tick_module, "fetch_klines", lambda symbol, timeframe, start: synthetic_ohlcv)

    db = SessionLocal()
    try:
        user = _make_user(db, "activeonly@example.com")
        active = _make_session(db, user, status="active")
        stopped = _make_session(db, user, status="stopped")

        processed = tick_module.run_all_active(db)

        assert processed == 1
        db.refresh(active)
        db.refresh(stopped)
        assert active.last_tick_at is not None
        assert stopped.last_tick_at is None
    finally:
        db.close()


def test_run_all_active_survives_one_session_failing(monkeypatch, synthetic_ohlcv):
    def _fake_fetch(symbol, timeframe, start):
        if symbol == "BROKEN":
            raise RuntimeError("símbolo inválido")
        return synthetic_ohlcv

    monkeypatch.setattr(tick_module, "fetch_klines", _fake_fetch)

    db = SessionLocal()
    try:
        user = _make_user(db, "partialfail@example.com")
        ok_session = _make_session(db, user, symbol="BTCUSDT")
        broken_session = _make_session(db, user, symbol="BROKEN")

        processed = tick_module.run_all_active(db)

        assert processed == 1
        db.refresh(ok_session)
        db.refresh(broken_session)
        assert ok_session.last_tick_at is not None
        assert broken_session.last_tick_at is None
    finally:
        db.close()
