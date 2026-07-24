#!/usr/bin/env python3
from __future__ import annotations

import argparse

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.core.strategy import get_strategy, list_strategies
from tradingos.data.loader import load_ohlcv
from tradingos.optimize.optimizer import run_grid_search
from tradingos.strategies.ma_crossover import default_config, example_grid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Corre un grid search sobre una estrategia registrada.")
    parser.add_argument("--strategy", required=True, help=f"Una de: {list_strategies()}")
    parser.add_argument("--data", required=True, help="Ruta a un archivo Parquet/CSV con columnas OHLCV")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--rank-by", default="profit_factor")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_ohlcv(args.data)

    strategy_cls = get_strategy(args.strategy)
    grid = example_grid()
    results = run_grid_search(strategy_cls, default_config(), grid, data, rank_by=args.rank_by)

    print(f"{len(results)} combinaciones evaluadas | top {args.top} por {args.rank_by}\n")
    for i, r in enumerate(results[: args.top], start=1):
        ema_fast = r.config.indicators["ema_fast"]["period"]
        ema_slow = r.config.indicators["ema_slow"]["period"]
        print(
            f"{i:>2}. ema_fast={ema_fast:<3} ema_slow={ema_slow:<3} stop_loss_pct={r.config.stop_loss_pct:<6} "
            f"PF={r.metrics['profit_factor']:.3f}  DD={r.metrics['max_drawdown']:.3f}  "
            f"trades={r.metrics['num_trades']}"
        )


if __name__ == "__main__":
    main()
