from datetime import datetime, timedelta

from tradingos.core.types import Side, Trade
from tradingos.montecarlo.simulator import run_monte_carlo


def _synthetic_trades(pnls: list[float]) -> list[Trade]:
    trades = []
    start = datetime(2024, 1, 1)
    for i, pnl in enumerate(pnls):
        entry = start + timedelta(hours=i)
        # ajustamos exit_price para que el pnl resultante sea exactamente el pedido
        trades.append(
            Trade(
                side=Side.LONG,
                entry_timestamp=entry,
                exit_timestamp=entry + timedelta(minutes=30),
                entry_price=100.0,
                exit_price=100.0 + pnl,
                quantity=1.0,
                commission=0.0,
            )
        )
    return trades


def test_run_monte_carlo_percentiles_are_ordered():
    trades = _synthetic_trades([10, -5, 20, -15, 8, -3, 12, -8, 5, -2])
    result = run_monte_carlo(trades, initial_equity=10_000.0, original_metrics={}, num_simulations=500, seed=42)

    equity_values = [result.final_equity_percentiles[f"p{p}"] for p in (5, 25, 50, 75, 95)]
    assert equity_values == sorted(equity_values)

    dd_values = [result.max_drawdown_percentiles[f"p{p}"] for p in (5, 25, 50, 75, 95)]
    assert dd_values == sorted(dd_values)

    assert 0.0 <= result.probability_of_profit <= 1.0


def test_run_monte_carlo_is_deterministic_with_seed():
    trades = _synthetic_trades([10, -5, 20, -15, 8])
    result_a = run_monte_carlo(trades, initial_equity=10_000.0, original_metrics={}, num_simulations=200, seed=7)
    result_b = run_monte_carlo(trades, initial_equity=10_000.0, original_metrics={}, num_simulations=200, seed=7)

    assert result_a.final_equity_percentiles == result_b.final_equity_percentiles
    assert result_a.max_drawdown_percentiles == result_b.max_drawdown_percentiles
    assert result_a.probability_of_profit == result_b.probability_of_profit


def test_run_monte_carlo_with_empty_trades_returns_degenerate_result():
    result = run_monte_carlo([], initial_equity=10_000.0, original_metrics={}, num_simulations=100, seed=1)

    assert all(v == 10_000.0 for v in result.final_equity_percentiles.values())
    assert all(v == 0.0 for v in result.max_drawdown_percentiles.values())
    assert result.probability_of_profit == 0.0
