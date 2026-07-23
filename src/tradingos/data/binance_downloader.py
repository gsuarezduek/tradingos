from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.binance.com/api/v3/klines"
MAX_LIMIT = 1000

# ms por intervalo, para paginar sin depender de que Binance devuelva el batch completo
_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}

_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "num_trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
)


def _to_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start: datetime, end: datetime | None = None) -> pd.DataFrame:
    """Descarga velas históricas de la API pública de Binance (sin autenticación), paginando."""
    if interval not in _INTERVAL_MS:
        raise ValueError(f"interval no soportado: {interval}. Usar uno de {sorted(_INTERVAL_MS)}")

    start_ms = _to_ms(start)
    end_ms = _to_ms(end) if end else _to_ms(datetime.now(timezone.utc))
    step_ms = _INTERVAL_MS[interval] * MAX_LIMIT

    frames: list[pd.DataFrame] = []
    cursor = start_ms
    session = requests.Session()

    while cursor < end_ms:
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": cursor,
            "endTime": min(cursor + step_ms, end_ms),
            "limit": MAX_LIMIT,
        }
        response = session.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            cursor += step_ms
            continue

        frames.append(pd.DataFrame(batch, columns=_COLUMNS))
        last_open_time = batch[-1][0]
        cursor = last_open_time + _INTERVAL_MS[interval]
        time.sleep(0.2)  # respetar rate limits de la API pública

    if not frames:
        raise RuntimeError(f"no se obtuvieron datos para {symbol} {interval} desde {start}")

    raw = pd.concat(frames, ignore_index=True)
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw["open_time"], unit="ms", utc=True),
            "open": raw["open"].astype(float),
            "high": raw["high"].astype(float),
            "low": raw["low"].astype(float),
            "close": raw["close"].astype(float),
            "volume": raw["volume"].astype(float),
        }
    )
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def download_and_save(symbol: str, interval: str, start: datetime, out_dir: str | Path, end: datetime | None = None) -> Path:
    df = fetch_klines(symbol, interval, start, end)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{symbol.upper()}_{interval}.parquet"
    df.to_parquet(out_path, index=False)
    return out_path
