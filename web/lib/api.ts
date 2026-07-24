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
