import pandas as pd

from tradingos.core.indicators import atr, ema, rsi, sma


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    result = sma(s, period=3)
    assert result.iloc[2] == 2.0
    assert result.iloc[3] == 3.0
    assert result.iloc[:2].isna().all()


def test_ema_converges_to_price_in_flat_series():
    s = pd.Series([10.0] * 20)
    result = ema(s, period=5)
    assert result.iloc[-1] == 10.0


def test_rsi_is_100_when_only_gains():
    s = pd.Series([float(i) for i in range(1, 20)])  # estrictamente creciente
    result = rsi(s, period=14)
    assert result.dropna().iloc[-1] == 100.0


def test_rsi_bounds():
    s = pd.Series([10, 12, 11, 13, 12, 15, 14, 16, 15, 18, 17, 19, 20, 22, 21, 23])
    result = rsi(s, period=14).dropna()
    assert (result >= 0).all() and (result <= 100).all()


def test_atr_zero_when_no_range():
    flat = pd.Series([100.0] * 20)
    result = atr(flat, flat, flat, period=5)
    assert result.dropna().eq(0.0).all()
