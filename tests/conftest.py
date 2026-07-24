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
