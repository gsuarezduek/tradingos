#!/usr/bin/env python3
from __future__ import annotations

import argparse

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import get_strategy, list_strategies
from tradingos.data.loader import load_ohlcv
from tradingos.strategies.ma_crossover import default_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Corre un backtest end-to-end sobre datos OHLCV.")
    parser.add_argument("--strategy", required=True, help=f"Una de: {list_strategies()}")
    parser.add_argument("--data", required=True, help="Ruta a un archivo Parquet/CSV con columnas OHLCV")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_ohlcv(args.data)

    strategy_cls = get_strategy(args.strategy)
    config = default_config(symbol=args.symbol, timeframe=args.timeframe)
    strategy = strategy_cls(config)

    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=args.initial_equity)
    result = engine.run(data)

    print(f"Estrategia: {args.strategy} | {args.symbol} {args.timeframe}")
    print(result.summary())


if __name__ == "__main__":
    main()
