#!/usr/bin/env python3
from __future__ import annotations

import argparse

import tradingos.strategies  # noqa: F401  (registra las estrategias disponibles)
from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.backtest.engine import BacktestEngine
from tradingos.core.strategy import get_strategy, list_strategies
from tradingos.data.loader import load_ohlcv
from tradingos.montecarlo.simulator import run_monte_carlo
from tradingos.strategies.ma_crossover import default_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Corre un backtest y simula Monte Carlo sobre sus trades.")
    parser.add_argument("--strategy", required=True, help=f"Una de: {list_strategies()}")
    parser.add_argument("--data", required=True, help="Ruta a un archivo Parquet/CSV con columnas OHLCV")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_ohlcv(args.data)

    strategy_cls = get_strategy(args.strategy)
    config = default_config(symbol=args.symbol, timeframe=args.timeframe)
    strategy = strategy_cls(config)

    engine = BacktestEngine(strategy, SimulatedBroker(BrokerSimConfig()), initial_equity=args.initial_equity)
    backtest_result = engine.run(data)

    mc_result = run_monte_carlo(
        backtest_result.trades,
        args.initial_equity,
        backtest_result.metrics,
        num_simulations=args.simulations,
        seed=args.seed,
    )

    print(f"Estrategia: {args.strategy} | {args.symbol} {args.timeframe} | {len(backtest_result.trades)} trades")
    print(f"Backtest real: PF={backtest_result.metrics['profit_factor']:.3f}  DD={backtest_result.metrics['max_drawdown']:.3f}\n")
    print(f"Monte Carlo ({args.simulations} simulaciones):")
    print("  Equity final:")
    for p, value in mc_result.final_equity_percentiles.items():
        print(f"    {p}: {value:,.2f}")
    print("  Max drawdown:")
    for p, value in mc_result.max_drawdown_percentiles.items():
        print(f"    {p}: {value:.3f}")
    print(f"  Probabilidad de profit: {mc_result.probability_of_profit:.1%}")


if __name__ == "__main__":
    main()
