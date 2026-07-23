from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    """Carga velas OHLCV desde un archivo Parquet o CSV y valida su esquema."""
    path = Path(path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path, parse_dates=["timestamp"])
    else:
        raise ValueError(f"formato de archivo no soportado: {path.suffix}")

    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"faltan columnas requeridas en {path}: {sorted(missing)}")

    df = df[list(REQUIRED_COLUMNS)].sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    if df["timestamp"].duplicated().any():
        raise ValueError(f"timestamps duplicados en {path}")

    return df
