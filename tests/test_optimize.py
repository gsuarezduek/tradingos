import tradingos.strategies  # noqa: F401  (registra ma_crossover)
from tradingos.core.strategy import get_strategy
from tradingos.optimize.grid import combination_count, expand_grid
from tradingos.optimize.optimizer import run_grid_search
from tradingos.strategies.ma_crossover import default_config


def test_expand_grid_produces_cartesian_product():
    grid = {"stop_loss_pct": [0.01, 0.02], "take_profit_pct": [0.03, 0.04, 0.05]}
    configs = expand_grid(default_config(), grid)
    assert len(configs) == 6
    assert combination_count(grid) == 6


def test_expand_grid_applies_nested_overrides():
    grid = {"indicators.ema_fast.period": [5, 10]}
    configs = expand_grid(default_config(), grid)
    periods = sorted(c.indicators["ema_fast"]["period"] for c in configs)
    assert periods == [5, 10]
    # el resto del config base no se toca
    assert all(c.indicators["ema_slow"]["period"] == 26 for c in configs)


def test_expand_grid_with_empty_grid_returns_base_config():
    base = default_config()
    assert expand_grid(base, {}) == [base]


def test_run_grid_search_returns_one_result_per_combination(synthetic_ohlcv):
    strategy_cls = get_strategy("ma_crossover")
    grid = {"indicators.ema_fast.period": [8, 12], "stop_loss_pct": [0.015, 0.02]}
    results = run_grid_search(strategy_cls, default_config(), grid, synthetic_ohlcv)
    assert len(results) == 4


def test_run_grid_search_is_sorted_descending_by_rank(synthetic_ohlcv):
    strategy_cls = get_strategy("ma_crossover")
    grid = {"indicators.ema_fast.period": [8, 10, 12, 16], "stop_loss_pct": [0.015, 0.02, 0.03]}
    results = run_grid_search(strategy_cls, default_config(), grid, synthetic_ohlcv, rank_by="profit_factor")
    scores = [r.metrics["profit_factor"] for r in results]
    assert scores == sorted(scores, reverse=True)
