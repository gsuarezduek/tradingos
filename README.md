# Trading OS — Núcleo de Research

Primer módulo de Trading OS (ver `Trading OS - Documento de Visión del Proyecto.pdf`):
Constructor de Estrategias + Motor de Backtesting + Métricas, sin capa SaaS ni ejecución
real todavía.

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Descargar datos históricos (API pública de Binance, sin auth)

```bash
.venv/bin/python scripts/download_binance_data.py --symbol BTCUSDT --interval 1h --start 2022-01-01
```

## Correr un backtest

```bash
.venv/bin/python scripts/run_backtest.py --strategy ma_crossover --data data/historical/BTCUSDT_1h.parquet
```

## Tests

```bash
.venv/bin/pytest
```

## Agregar una estrategia nueva

1. Crear un archivo en `src/tradingos/strategies/`.
2. Subclasear `tradingos.core.strategy.Strategy`, definir `prepare()` (indicadores) y
   `on_bar()` (condiciones de entrada/salida).
3. Decorarla con `@register_strategy("nombre")`.
4. Importarla desde `src/tradingos/strategies/__init__.py`.

El motor de backtesting (`tradingos.backtest.engine.BacktestEngine`) nunca se modifica:
aplica el SL/TP/trailing/dimensionamiento por riesgo definidos en `StrategyConfig` de
forma centralizada para todas las estrategias.

## Arquitectura

```
src/tradingos/
  core/       # tipos de dominio, contrato de Strategy, indicadores, gestión de riesgo
  data/       # descarga y carga de datos OHLCV
  backtest/   # motor event-driven, simulación de broker, métricas, resultado
  strategies/ # estrategias concretas (plug-in, sin tocar el núcleo)
scripts/      # CLIs: descarga de datos y corrida de backtests
tests/
```
