export interface EquityPoint {
  timestamp: string;
  equity: number;
}

export interface LiveBacktestMetrics {
  profit_factor: number;
  win_rate: number;
  expectancy: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  cagr: number;
  avg_monthly_return: number;
  avg_risk_per_trade: number;
  num_trades: number;
}

export interface LiveBacktest {
  numTrades: number;
  metrics: LiveBacktestMetrics;
  equityCurve: EquityPoint[];
}

const API_BASE_URL = process.env.API_BASE_URL ?? "https://tradingos-production.up.railway.app";

// Backtest fijo (ma_crossover sobre BTCUSDT 1h) servido por GET /backtests/demo.
// Se cachea 5 minutos: es un resultado histórico, no cambia seguido. Si la API no
// responde a tiempo, devuelve null y quien llama debe caer a datos de ejemplo.
export async function getLiveBacktest(): Promise<LiveBacktest | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/backtests/demo`, {
      signal: AbortSignal.timeout(5000),
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;

    const data = await response.json();
    return {
      numTrades: data.num_trades,
      metrics: data.metrics,
      equityCurve: data.equity_curve,
    };
  } catch {
    return null;
  }
}

export interface OptimizationRow {
  emaFastPeriod: number;
  stopLossPct: number;
  profitFactor: number;
  maxDrawdownPct: number;
  numTrades: number;
}

export interface LiveOptimization {
  totalCombinations: number;
  results: OptimizationRow[];
}

// Grid search fijo (ma_crossover sobre BTCUSDT 1h) servido por GET /optimize/demo.
// A diferencia de /backtests/demo, acá el timeout es más generoso (20s, no 5s): corre
// 2 backtests reales en vez de uno, y medido en producción ese endpoint solo ya tardó
// hasta ~15s (single-worker, variable según carga del proceso).
export async function getLiveOptimization(): Promise<LiveOptimization | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/optimize/demo`, {
      signal: AbortSignal.timeout(20000),
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;

    const data = await response.json();
    return {
      totalCombinations: data.total_combinations,
      results: data.results.map(
        (r: { config: { indicators: { ema_fast: { period: number } }; stop_loss_pct: number }; metrics: { profit_factor: number; max_drawdown: number; num_trades: number } }) => ({
          emaFastPeriod: r.config.indicators.ema_fast.period,
          stopLossPct: r.config.stop_loss_pct,
          profitFactor: r.metrics.profit_factor,
          maxDrawdownPct: r.metrics.max_drawdown * 100,
          numTrades: r.metrics.num_trades,
        }),
      ),
    };
  } catch {
    return null;
  }
}

export type PercentileKey = "p5" | "p25" | "p50" | "p75" | "p95";
export type Percentiles = Record<PercentileKey, number>;

export interface LiveMonteCarlo {
  numSimulations: number;
  initialEquity: number;
  originalMetrics: LiveBacktestMetrics;
  finalEquityPercentiles: Percentiles;
  maxDrawdownPercentiles: Percentiles;
  probabilityOfProfit: number;
}

// Monte Carlo fijo (ma_crossover sobre BTCUSDT 1h) servido por GET /montecarlo/demo.
// Mismo motivo que /optimize/demo: el costo dominante es el backtest previo, que en
// producción se midió hasta ~15s (single-worker, variable según carga del proceso).
export async function getLiveMonteCarlo(): Promise<LiveMonteCarlo | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/montecarlo/demo`, {
      signal: AbortSignal.timeout(20000),
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;

    const data = await response.json();
    return {
      numSimulations: data.num_simulations,
      initialEquity: data.initial_equity,
      originalMetrics: data.original_metrics,
      finalEquityPercentiles: data.final_equity_percentiles,
      maxDrawdownPercentiles: data.max_drawdown_percentiles,
      probabilityOfProfit: data.probability_of_profit,
    };
  } catch {
    return null;
  }
}
