import pandas as pd

from tradingos.core.indicators import adx, atr, bollinger_bands, ema, macd, rsi, sma


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


def test_macd_is_zero_on_flat_series():
    flat = pd.Series([100.0] * 60)
    macd_line, signal_line, histogram = macd(flat, fast_period=12, slow_period=26, signal_period=9)
    assert macd_line.dropna().eq(0.0).all()
    assert signal_line.dropna().eq(0.0).all()
    assert histogram.dropna().eq(0.0).all()


def test_macd_positive_on_uptrend():
    uptrend = pd.Series([100.0 + i for i in range(60)])
    macd_line, _, _ = macd(uptrend, fast_period=12, slow_period=26, signal_period=9)
    # EMA rápida reacciona más rápido que la lenta: en una tendencia sostenida al alza
    # queda por encima -> macd_line positiva.
    assert macd_line.dropna().iloc[-1] > 0


def test_bollinger_bands_widen_with_volatility():
    flat = pd.Series([100.0] * 25)
    middle, upper, lower = bollinger_bands(flat, period=20, num_std=2.0)
    assert upper.dropna().eq(middle.dropna()).all()
    assert lower.dropna().eq(middle.dropna()).all()

    volatile = pd.Series([100.0, 110.0] * 13)
    _, upper_v, lower_v = bollinger_bands(volatile, period=20, num_std=2.0)
    assert (upper_v.dropna() > lower_v.dropna()).all()


def test_adx_strong_uptrend_has_higher_plus_di():
    close = pd.Series([100.0 + i for i in range(60)])
    high = close + 0.5
    low = close - 0.5

    adx_line, plus_di, minus_di = adx(high, low, close, period=14)

    assert plus_di.dropna().iloc[-1] > minus_di.dropna().iloc[-1]
    # Tendencia monótona sin ninguna pullback: es el caso de máxima fuerza de tendencia.
    assert adx_line.dropna().iloc[-1] > 50


def test_adx_handles_flat_series_without_dividing_by_zero():
    flat = pd.Series([100.0] * 30)

    adx_line, plus_di, minus_di = adx(flat, flat, flat, period=14)

    # Sin ningún rango, +DI/-DI/ADX quedan indefinidos (NaN) en vez de explotar por
    # división por cero.
    assert adx_line.isna().all()
    assert plus_di.isna().all()
    assert minus_di.isna().all()


def test_adx_bounds_with_mixed_movement():
    close = pd.Series([10, 12, 11, 13, 12, 15, 14, 16, 15, 18, 17, 19, 20, 22, 21, 23, 22, 25, 24, 27], dtype=float)
    high = close + 1
    low = close - 1

    adx_line, plus_di, minus_di = adx(high, low, close, period=14)

    assert (plus_di.dropna() >= 0).all() and (plus_di.dropna() <= 100).all()
    assert (minus_di.dropna() >= 0).all() and (minus_di.dropna() <= 100).all()
    assert (adx_line.dropna() >= 0).all() and (adx_line.dropna() <= 100).all()
