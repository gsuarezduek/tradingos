# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este repo

Trading OS: SaaS de trading algorítmico (ver `Trading OS - Documento de Visión del
Proyecto.pdf`). Este repo contiene el backend Python (`src/tradingos`, API FastAPI +
Postgres/SQLite) y el frontend Next.js (`web/`). Ya incluye capa SaaS real: auth de
usuarios, conexión de exchanges, paper trading y estrategias guardadas persistidas en
DB — no es solo el núcleo de research.

`web/` tiene su propio `CLAUDE.md`/`AGENTS.md` con una instrucción específica sobre esa
versión de Next.js (leer los docs bundleados en `node_modules/next/dist/docs/` antes de
tocar código ahí, por breaking changes respecto al Next.js "de memoria").

## Comandos

### Backend (Python)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/pytest                                    # todos los tests
.venv/bin/pytest tests/test_engine.py                # un archivo
.venv/bin/pytest tests/test_engine.py::test_nombre   # un test puntual
.venv/bin/pytest -k nombre_parcial                   # por nombre parcial

.venv/bin/uvicorn tradingos.api.main:app --reload    # levantar la API local

.venv/bin/python scripts/download_binance_data.py --symbol BTCUSDT --interval 1h --start 2022-01-01
.venv/bin/python scripts/run_backtest.py --strategy ma_crossover --data data/historical/BTCUSDT_1h.parquet
.venv/bin/python scripts/run_optimization.py
.venv/bin/python scripts/run_montecarlo.py
.venv/bin/python scripts/run_paper_trading_tick.py

.venv/bin/alembic revision --autogenerate -m "descripción"   # nueva migración tras cambiar db/models.py
.venv/bin/alembic upgrade head                                # aplicar migraciones (la API también lo hace sola al arrancar)
```

No hay linter/type-checker configurado para Python (sin ruff/mypy en `pyproject.toml`).

### Frontend (`web/`)

```bash
npm run dev      # dev server
npm run build
npm run lint      # eslint
```

## Arquitectura backend

```
src/tradingos/
  core/        # StrategyConfig, contrato Strategy (ABC), StrategyContext, indicadores, risk sizing
  data/        # descarga (Binance REST pública) y carga de OHLCV (parquet)
  backtest/    # engine event-driven, broker_sim, metrics, result, service (helpers compartidos con la API)
  strategies/  # estrategias concretas registradas vía @register_strategy
  optimize/    # grid search sobre StrategyConfig
  montecarlo/  # resampling de trades de un backtest ya corrido (no re-corre el engine)
  paper_trading/  # tick loop que reusa el broker_sim del backtest sobre precio en vivo
  connectors/  # clientes REST por exchange (binance, bingx, bitget, mexc) — sin registry, se listan a mano en api/routers/brokers.py
  auth/        # JWT (security.py) + dependency get_current_user (dependencies.py)
  db/          # SQLAlchemy models, session (Postgres prod / SQLite dev), migrate.py (alembic upgrade head)
  api/         # FastAPI app + routers (auth, brokers, paper_trading, strategies)
scripts/       # CLIs finos sobre las funciones de src/tradingos
```

**El motor de backtesting (`tradingos.backtest.engine.BacktestEngine`) no se
modifica por estrategia**: aplica SL/TP/trailing/dimensionamiento por riesgo definidos
en `StrategyConfig` de forma centralizada para todas las estrategias.

### Agregar una estrategia nueva

1. Archivo nuevo en `src/tradingos/strategies/`.
2. Subclasear `tradingos.core.strategy.Strategy`: `prepare()` (calcula indicadores sobre
   el DataFrame OHLCV) y `on_bar()` (devuelve una `Signal` o `None` por barra, leyendo
   `StrategyContext.history`/`current_index`/`position`/`equity`).
3. Decorar con `@register_strategy("nombre")`.
4. Importarla desde `src/tradingos/strategies/__init__.py` (si no se importa, no queda
   registrada — `api/main.py` importa el paquete completo al arrancar para forzar esto).

### Modelo de datos (`db/models.py`)

- `User` → `BrokerConnection` (credenciales de exchange, cifradas con Fernet vía
  `db/crypto.py`, nunca en plaintext), `PaperTradingSession` (+ `PaperTrade` hijos),
  `SavedStrategy` (+ `StrategyBacktestRun` hijos).
- `SavedStrategy.symbols`/`timeframes` son metadata declarativa del usuario — no
  implican que exista un dataset real para correr un backtest en esa combinación; eso
  se valida aparte contra los datasets disponibles en `TRADINGOS_DATA_DIR`.
- `StrategyBacktestRun` guarda un snapshot inmutable por corrida (`config_snapshot`,
  `trades` como JSON) para que editar la estrategia después no reescriba el historial.
- Cambios en `db/models.py` requieren una migración Alembic nueva (`alembic revision
  --autogenerate`) — `run_migrations()` corre `alembic upgrade head` automáticamente en
  el lifespan de la API, tanto en dev como en producción, así que nunca hace falta (ni
  se debe) usar `Base.metadata.create_all()`.

### Auth

JWT Bearer. `get_current_user` (dependency de FastAPI) decodifica el token y resuelve
el `User` desde la DB; los routers que necesitan sesión lo inyectan como dependencia.

### Conectores de exchanges

Sin registry como las estrategias: cada exchange tiene su módulo en `connectors/` y se
lista a mano en `_EXCHANGES` (`api/routers/brokers.py`) con sus funciones de
spot/futures/precios. Las credenciales de exchange nunca se persisten en plaintext ni
se loguean — viven solo dentro de la llamada que las usa.

### Límites de cómputo en la API

`api/main.py` define topes explícitos (`MAX_GRID_COMBINATIONS`,
`MAX_MONTE_CARLO_SIMULATIONS`) porque el servidor corre un solo proceso/worker: un
backtest real tarda ~8s en producción, y un endpoint lento bloquea el resto del tráfico
mientras corre (no es solo un tema de timeout del cliente). Los endpoints `/*/demo`
existen para alimentar el dashboard sin que el cliente arme un request completo, y usan
grillas/datasets deliberadamente chicos por el mismo motivo.

## Arquitectura frontend (`web/`)

Next.js App Router, server components por default. `web/lib/session.ts` maneja la
cookie de sesión (`tradingos_session`, httpOnly) del lado del servidor; `web/lib/api.ts`
concentra los fetches al backend (`API_BASE_URL`, con fallback a demo data cuando la
API no responde a tiempo). Cada módulo vive en su propia carpeta bajo `web/app/`
(`constructor/`, `paper-trading/`, `conexiones/`, `optimizador/`, `montecarlo/`), con un
`page.tsx` server component que hace fetch inicial y un `*Client.tsx` con la interacción.

## Despliegue

Railway (proyecto `tradingos`, dominio `trading.alphaswap.me`). `Dockerfile` empaqueta
solo el backend (instala el paquete y corre uvicorn); en producción `DATABASE_URL`
apunta a Postgres vía variable de referencia de Railway, en local cae a SQLite
(`sqlite:///./tradingos.db`).
