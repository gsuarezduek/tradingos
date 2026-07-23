// Datos de ejemplo (dummy) para el dashboard inicial.
// Ningún valor de este archivo viene de datos reales todavía: no hay backtests
// persistidos, ni cuentas de exchange conectadas, ni motor de ejecución corriendo.
// Cuando exista esa integración, este archivo se reemplaza por llamadas a la API
// (por ahora en https://tradingos-production.up.railway.app).

export const IS_DUMMY_DATA = true;

export const weeklyPnl = [
  { label: "Lun", value: 4 },
  { label: "Mar", value: 9 },
  { label: "Mié", value: 7 },
  { label: "Jue", value: 3 },
  { label: "Vie", value: 8 },
];

export const summary = {
  winRatePct: 61,
  capitalActual: 24310,
  operacionesAbiertas: 6,
  operacionesCerradas: 128,
  drawdownPct: 9.4,
  gananciaMensualPct: 5.2,
};

export type StrategyStatus = "activas" | "paper" | "backtesting" | "pausadas";

export interface DummyStrategy {
  id: string;
  name: string;
  description: string;
  symbol: string;
  timeframe: string;
  status: StrategyStatus;
  profitFactor: number;
  maxDrawdownPct: number;
  updatedAt: string;
}

export const strategies: DummyStrategy[] = [
  {
    id: "1",
    name: "EMA Crossover BTC",
    description: "Cruce de EMA 12/26 con filtro de volatilidad por ATR",
    symbol: "BTCUSDT",
    timeframe: "1h",
    status: "activas",
    profitFactor: 1.42,
    maxDrawdownPct: 12.1,
    updatedAt: "18 Jul",
  },
  {
    id: "2",
    name: "Mean Reversion ETH",
    description: "Reversión a la media sobre bandas de Bollinger",
    symbol: "ETHUSDT",
    timeframe: "4h",
    status: "activas",
    profitFactor: 1.18,
    maxDrawdownPct: 15.7,
    updatedAt: "20 Jul",
  },
  {
    id: "3",
    name: "Breakout Rangos SOL",
    description: "Ruptura de rango con confirmación de volumen",
    symbol: "SOLUSDT",
    timeframe: "15m",
    status: "paper",
    profitFactor: 1.05,
    maxDrawdownPct: 8.3,
    updatedAt: "22 Jul",
  },
  {
    id: "4",
    name: "RSI Extremos BTC",
    description: "Entradas en sobreventa/sobrecompra con SL dinámico",
    symbol: "BTCUSDT",
    timeframe: "1d",
    status: "backtesting",
    profitFactor: 0.94,
    maxDrawdownPct: 21.4,
    updatedAt: "15 Jul",
  },
  {
    id: "5",
    name: "Grid Neutral ETH",
    description: "Grid trading en rango lateral detectado",
    symbol: "ETHUSDT",
    timeframe: "1h",
    status: "backtesting",
    profitFactor: 1.11,
    maxDrawdownPct: 10.9,
    updatedAt: "12 Jul",
  },
  {
    id: "6",
    name: "Momentum Altcoins",
    description: "Pausada tras deterioro del Sharpe en el último mes",
    symbol: "Multi",
    timeframe: "4h",
    status: "pausadas",
    profitFactor: 0.71,
    maxDrawdownPct: 28.6,
    updatedAt: "02 Jul",
  },
];

export const strategyColumns: { key: StrategyStatus; label: string }[] = [
  { key: "activas", label: "Activas" },
  { key: "paper", label: "Paper Trading" },
  { key: "backtesting", label: "En Backtesting" },
  { key: "pausadas", label: "Pausadas" },
];
