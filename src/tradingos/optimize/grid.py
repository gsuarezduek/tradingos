from __future__ import annotations

import itertools
from typing import Any

from tradingos.core.strategy import StrategyConfig

ParameterGrid = dict[str, list[Any]]


def _set_by_path(data: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    target = data
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def combination_count(grid: ParameterGrid) -> int:
    count = 1
    for values in grid.values():
        count *= len(values)
    return count


def expand_grid(base_config: StrategyConfig, grid: ParameterGrid) -> list[StrategyConfig]:
    """Genera una StrategyConfig por cada combinación del producto cartesiano de `grid`.

    Las claves de `grid` son rutas separadas por punto dentro del config (ej.
    "stop_loss_pct" o "indicators.ema_fast.period").
    """
    if not grid:
        return [base_config]

    keys = list(grid.keys())
    value_lists = [grid[key] for key in keys]

    configs = []
    for combination in itertools.product(*value_lists):
        data = base_config.model_dump()
        for path, value in zip(keys, combination):
            _set_by_path(data, path, value)
        configs.append(StrategyConfig(**data))
    return configs
