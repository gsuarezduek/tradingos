#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from tradingos.data.binance_downloader import download_and_save

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "historical"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga velas históricas públicas de Binance a Parquet.")
    parser.add_argument("--symbol", required=True, help="Ej: BTCUSDT")
    parser.add_argument("--interval", required=True, help="Ej: 1h, 1d, 15m")
    parser.add_argument("--start", required=True, help="Fecha de inicio, formato YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="Fecha de fin, formato YYYY-MM-DD (default: ahora)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.end else None

    path = download_and_save(args.symbol, args.interval, start, args.out_dir, end)
    print(f"Datos guardados en {path}")


if __name__ == "__main__":
    main()
