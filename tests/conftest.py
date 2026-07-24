import os

# Tiene que setearse antes de que cualquier test importe tradingos.api.main (que a su
# vez importa tradingos.db.session, donde se lee DATABASE_URL a nivel de módulo).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-at-least-32-bytes-long")
os.environ.setdefault("ENCRYPTION_KEY", "2l1htVa-fcs-u_vakta0b7uMkvQxdBm8mf5BbP9zMD8=")

import numpy as np
import pandas as pd
import pytest


def _synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    flat = np.full(40, 100.0)
    uptrend = 100.0 + np.cumsum(rng.uniform(0.3, 1.2, size=110))
    downtrend = uptrend[-1] - np.cumsum(rng.uniform(0.3, 1.2, size=110))
    tail = np.full(40, downtrend[-1])
    close = np.concatenate([flat, uptrend, downtrend, tail])[:n]

    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2023-01-01", periods=len(close), freq="h", tz="UTC"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(len(close), 1000.0),
        }
    )


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv()


@pytest.fixture(autouse=True)
def _reset_db():
    """Aisla cada test: recrea el schema antes y lo tira después. Es barato porque
    DATABASE_URL en tests apunta a sqlite en memoria (ver arriba)."""
    from tradingos.db.models import Base
    from tradingos.db.session import engine

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
