from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))
    return result.where(avg_loss != 0, 100.0)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def macd(
    series: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devuelve (línea MACD, línea de señal, histograma)."""
    macd_line = ema(series, fast_period) - ema(series, slow_period)
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devuelve (banda media, banda superior, banda inferior)."""
    middle = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return middle, upper, lower


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devuelve (ADX, +DI, -DI) por el método de Wilder — mismo suavizado que `atr`."""
    prev_close = close.shift(1)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    smoothed_tr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    smoothed_plus_dm = plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    smoothed_minus_dm = minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * smoothed_plus_dm / smoothed_tr.replace(0, float("nan"))
    minus_di = 100 * smoothed_minus_dm / smoothed_tr.replace(0, float("nan"))

    # di_sum == 0 real (sin movimiento direccional) -> DX 0, no división por cero; NaN
    # de warm-up se preserva porque NaN != 0 es True y .where() no lo toca.
    di_sum = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / di_sum.where(di_sum != 0, 1.0)
    adx_line = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    return adx_line, plus_di, minus_di
