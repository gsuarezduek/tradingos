"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { TopMetricsPanel } from "@/components/TopMetricsPanel";
import type { LiveBacktestMetrics } from "@/lib/api";
import { conditionLabel, type Condition, type ConditionCategory, type DatasetOption } from "../ConstructorClient";

interface StrategyConfigJSON {
  symbol: string;
  timeframe: string;
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  trailing_stop_pct: number | null;
  risk_per_trade: number;
  position_sizing: { method: string };
  indicators: Record<string, Record<string, number>>;
}

interface BacktestRunSummary {
  id: number;
  symbol: string;
  timeframe: string;
  dataset: string;
  initial_equity: number;
  range_start: string | null;
  range_end: string | null;
  num_trades: number;
  metrics: LiveBacktestMetrics;
  total_pnl: number;
  created_at: string;
}

interface Trade {
  side: string;
  entry_timestamp: string;
  exit_timestamp: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  commission: number;
  pnl: number;
}

interface BacktestRunDetail extends BacktestRunSummary {
  config_snapshot: StrategyConfigJSON;
  equity_curve: { timestamp: string; equity: number }[];
  trades: Trade[];
}

export interface StrategyDetail {
  id: number;
  name: string;
  strategy_type: string;
  category: string;
  symbols: string[];
  timeframes: string[];
  entry_conditions: string;
  exit_conditions: string;
  entry_rules: Condition[];
  exit_rules: Condition[];
  config: StrategyConfigJSON;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
  backtest_runs: BacktestRunSummary[];
}

const CATEGORY_LABELS: Record<string, string> = {
  scalping: "Scalping",
  day_trading: "Day Trading",
  swing: "Swing",
};

function ConfigField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted">{label}</span>
      <span className="text-sm font-semibold text-ink">{value}</span>
    </div>
  );
}

function pct(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toLocaleString("es-AR", { maximumFractionDigits: 2 })}%`;
}

export function StrategyDetailClient({
  strategyId,
  initialStrategy,
  initialError,
  datasets,
  conditionCatalog,
}: {
  strategyId: string;
  initialStrategy: StrategyDetail | null;
  initialError: string | null;
  datasets: DatasetOption[];
  conditionCatalog: ConditionCategory[];
}) {
  const [strategy, setStrategy] = useState<StrategyDetail | null>(initialStrategy);
  const [loadError] = useState<string | null>(initialError);
  const [togglingStatus, setTogglingStatus] = useState(false);

  // strategy/datasets llegan resueltos desde el server component: alcanza con derivar
  // el combo inicial una sola vez al montar, no hace falta un efecto para eso.
  const initialValidCombos = initialStrategy
    ? datasets.filter((d) => initialStrategy.symbols.includes(d.symbol) && initialStrategy.timeframes.includes(d.timeframe))
    : [];
  const [runSymbol, setRunSymbol] = useState(initialValidCombos[0]?.symbol ?? "");
  const [runTimeframe, setRunTimeframe] = useState(initialValidCombos[0]?.timeframe ?? "");
  const [runInitialEquity, setRunInitialEquity] = useState(10000);
  // Vacío = usar todo el histórico disponible del dataset.
  const [runStartDate, setRunStartDate] = useState("");
  const [runEndDate, setRunEndDate] = useState("");
  const [runningBacktest, setRunningBacktest] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(strategy?.backtest_runs[0]?.id ?? null);
  const [selectedRunDetail, setSelectedRunDetail] = useState<BacktestRunDetail | null>(null);

  const validCombos = strategy
    ? datasets.filter((d) => strategy.symbols.includes(d.symbol) && strategy.timeframes.includes(d.timeframe))
    : [];

  useEffect(() => {
    if (selectedRunId == null || !strategy) return;
    let cancelled = false;
    fetch(`/api/strategies/${strategy.id}/backtests/${selectedRunId}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setSelectedRunDetail(data);
      })
      .catch(() => {
        if (!cancelled) setSelectedRunDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRunId, strategy]);

  async function reloadStrategy() {
    const response = await fetch(`/api/strategies/${strategyId}`);
    const data = await response.json();
    if (response.ok) setStrategy(data);
  }

  async function toggleStatus() {
    if (!strategy) return;
    setTogglingStatus(true);
    try {
      const nextStatus = strategy.status === "active" ? "paused" : "active";
      await fetch(`/api/strategies/${strategy.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      await reloadStrategy();
    } finally {
      setTogglingStatus(false);
    }
  }

  async function runNewBacktest() {
    if (!strategy || !runSymbol || !runTimeframe) return;
    setRunningBacktest(true);
    setRunError(null);
    try {
      const response = await fetch(`/api/strategies/${strategy.id}/backtests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: runSymbol,
          timeframe: runTimeframe,
          initial_equity: runInitialEquity,
          start_date: runStartDate || null,
          end_date: runEndDate || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setRunError(typeof data.detail === "string" ? data.detail : "No se pudo correr el backtest.");
        return;
      }
      await reloadStrategy();
      setSelectedRunId(data.id);
    } catch {
      setRunError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setRunningBacktest(false);
    }
  }

  if (loadError || !strategy) {
    return (
      <div className="flex flex-col gap-8">
        <Link href="/constructor" className="text-sm font-semibold text-ink underline">
          ← Volver al Constructor de Estrategias
        </Link>
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo cargar la estrategia: </span>
          {loadError ?? "estrategia no encontrada"}
        </div>
      </div>
    );
  }

  const isActive = strategy.status === "active";
  const selectedDataset = validCombos.find((d) => d.symbol === runSymbol && d.timeframe === runTimeframe) ?? null;
  const trades = selectedRunDetail?.trades ?? [];
  const chartData = (selectedRunDetail?.equity_curve ?? []).slice(-5).map((point) => ({
    label: new Date(point.timestamp).toLocaleString("es-AR", { day: "2-digit", month: "2-digit" }),
    value: point.equity,
  }));
  const config = strategy.config;
  const emaFast = config.indicators?.ema_fast?.period;
  const emaSlow = config.indicators?.ema_slow?.period;
  const atr = config.indicators?.atr?.period;
  const atrMinPct = config.indicators?.atr?.min_value_pct;

  return (
    <div className="flex flex-col gap-8">
      <Link href="/constructor" className="text-sm font-semibold text-ink underline">
        ← Volver al Constructor de Estrategias
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            {strategy.name}
            <InfoGuide>
              Esta pantalla muestra la estrategia guardada (categoría, mercados, temporalidades, condiciones
              y parámetros técnicos) junto con el historial completo de backtests corridos contra ella.
              Elegí símbolo/timeframe entre los que declaraste (y para los que hay dataset real), opcionalmente
              acotá el rango de fechas a probar, y corré un nuevo backtest cuando quieras: cada corrida queda
              guardada, no reemplaza a las anteriores. Hacé clic en una fila del historial para ver su curva
              de equity y sus operaciones (con precio de entrada/salida de cada una, para poder auditar que
              la estrategia esté operando como esperás).
            </InfoGuide>
          </h1>
          <p className="text-xs text-muted">
            {CATEGORY_LABELS[strategy.category] ?? strategy.category} · {strategy.symbols.join(", ")} ·{" "}
            {strategy.timeframes.join(", ")} · guardada:{" "}
            {new Date(strategy.created_at).toLocaleString("es-AR")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <DataBadge live={isActive} label={isActive ? "Activa" : "Pausada"} />
          <button
            onClick={toggleStatus}
            disabled={togglingStatus}
            className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted disabled:opacity-50"
          >
            {togglingStatus ? "Actualizando…" : isActive ? "Pausar" : "Activar"}
          </button>
        </div>
      </div>

      {selectedRunDetail && (
        <TopMetricsPanel
          chartTitle="Equity de la corrida seleccionada"
          chartData={chartData}
          winRatePct={selectedRunDetail.metrics.win_rate * 100}
          capitalActual={selectedRunDetail.equity_curve.at(-1)?.equity ?? selectedRunDetail.initial_equity}
          statLabel="Operaciones cerradas"
          statValue={String(selectedRunDetail.num_trades)}
          live
        />
      )}

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Definición de la estrategia</h2>

        {strategy.strategy_type === "condition_based" ? (
          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <ConfigField label="Stop Loss" value={pct(config.stop_loss_pct)} />
            <ConfigField label="Take Profit" value={pct(config.take_profit_pct)} />
            <ConfigField label="Trailing Stop" value={pct(config.trailing_stop_pct)} />
            <ConfigField label="Riesgo por operación" value={pct(config.risk_per_trade)} />
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <ConfigField label="EMA rápida" value={emaFast != null ? String(emaFast) : "—"} />
            <ConfigField label="EMA lenta" value={emaSlow != null ? String(emaSlow) : "—"} />
            <ConfigField label="ATR (períodos)" value={atr != null ? String(atr) : "—"} />
            <ConfigField label="ATR mínimo" value={pct(atrMinPct)} />
            <ConfigField label="Stop Loss" value={pct(config.stop_loss_pct)} />
            <ConfigField label="Take Profit" value={pct(config.take_profit_pct)} />
            <ConfigField label="Trailing Stop" value={pct(config.trailing_stop_pct)} />
            <ConfigField label="Riesgo por operación" value={pct(config.risk_per_trade)} />
          </div>
        )}

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <span className="text-xs font-medium text-muted">Condiciones de entrada</span>
            {strategy.entry_rules.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-2">
                {strategy.entry_rules.map((c, i) => (
                  <span
                    key={i}
                    className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-ink"
                  >
                    {conditionLabel(conditionCatalog, c)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-sm text-ink">{strategy.entry_conditions || "—"}</p>
            )}
          </div>
          <div>
            <span className="text-xs font-medium text-muted">Condiciones de salida</span>
            {strategy.exit_rules.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-2">
                {strategy.exit_rules.map((c, i) => (
                  <span
                    key={i}
                    className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-ink"
                  >
                    {conditionLabel(conditionCatalog, c)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-sm text-ink">{strategy.exit_conditions || "—"}</p>
            )}
          </div>
        </div>

        {strategy.notes && (
          <div className="mt-4">
            <span className="text-xs font-medium text-muted">Notas</span>
            <p className="mt-1 text-sm text-ink">{strategy.notes}</p>
          </div>
        )}
      </div>

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Correr nuevo backtest</h2>

        {validCombos.length === 0 && (
          <p className="mt-2 text-sm text-muted">
            No hay dataset disponible para ninguno de los mercados/temporalidades de esta estrategia.
          </p>
        )}

        {validCombos.length > 0 && (
          <div className="mt-4 flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Símbolo · Timeframe</span>
              <select
                value={`${runSymbol}|${runTimeframe}`}
                onChange={(e) => {
                  const [sym, tf] = e.target.value.split("|");
                  setRunSymbol(sym);
                  setRunTimeframe(tf);
                }}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              >
                {validCombos.map((c) => (
                  <option key={`${c.symbol}|${c.timeframe}`} value={`${c.symbol}|${c.timeframe}`}>
                    {c.symbol} · {c.timeframe}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Equity inicial ($)</span>
              <input
                type="number"
                min="100"
                step="100"
                value={runInitialEquity}
                onChange={(e) => setRunInitialEquity(Number(e.target.value))}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Desde</span>
              <input
                type="date"
                value={runStartDate}
                min={selectedDataset?.start.slice(0, 10)}
                max={selectedDataset?.end.slice(0, 10)}
                onChange={(e) => setRunStartDate(e.target.value)}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Hasta</span>
              <input
                type="date"
                value={runEndDate}
                min={selectedDataset?.start.slice(0, 10)}
                max={selectedDataset?.end.slice(0, 10)}
                onChange={(e) => setRunEndDate(e.target.value)}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
            <button
              onClick={runNewBacktest}
              disabled={runningBacktest}
              className="rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {runningBacktest ? "Corriendo…" : "Correr backtest"}
            </button>
          </div>
        )}

        {validCombos.length > 0 && selectedDataset && (
          <p className="mt-2 text-xs text-muted">
            Datos disponibles para {selectedDataset.symbol} · {selectedDataset.timeframe}: desde{" "}
            {new Date(selectedDataset.start).toLocaleDateString("es-AR")} hasta{" "}
            {new Date(selectedDataset.end).toLocaleDateString("es-AR")}. Dejá las fechas vacías para usar todo el
            histórico.
          </p>
        )}

        {runError && (
          <p className="mt-4 text-sm text-muted">
            <span className="font-semibold text-ink">No se pudo correr: </span>
            {runError}
          </p>
        )}
      </div>

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Historial de backtests</h2>

        {strategy.backtest_runs.length === 0 && <p className="mt-4 text-sm text-muted">Todavía no se corrió ningún backtest.</p>}

        {strategy.backtest_runs.length > 0 && (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Fecha</th>
                  <th className="pb-2 pr-4 font-medium">Símbolo</th>
                  <th className="pb-2 pr-4 font-medium">Timeframe</th>
                  <th className="pb-2 pr-4 font-medium">Operaciones</th>
                  <th className="pb-2 pr-4 font-medium">Win rate</th>
                  <th className="pb-2 pr-4 font-medium">Profit factor</th>
                  <th className="pb-2 pr-4 font-medium">PnL total</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {strategy.backtest_runs.map((run) => (
                  <tr key={run.id} className="border-b border-border last:border-0">
                    <td className="py-3 pr-4 text-muted">{new Date(run.created_at).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
                    <td className="py-3 pr-4 font-semibold text-ink">{run.symbol}</td>
                    <td className="py-3 pr-4 text-ink">{run.timeframe}</td>
                    <td className="py-3 pr-4 text-ink">{run.num_trades}</td>
                    <td className="py-3 pr-4 text-ink">{(run.metrics.win_rate * 100).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%</td>
                    <td className="py-3 pr-4 text-ink">{run.metrics.profit_factor.toLocaleString("es-AR", { maximumFractionDigits: 2 })}</td>
                    <td className={`py-3 pr-4 font-semibold ${run.total_pnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                      {run.total_pnl >= 0 ? "+" : ""}
                      {run.total_pnl.toLocaleString("es-AR", { maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-3">
                      <button
                        onClick={() => setSelectedRunId(run.id)}
                        className={`text-sm font-semibold underline ${selectedRunId === run.id ? "text-ink" : "text-muted"}`}
                      >
                        {selectedRunId === run.id ? "Viendo" : "Ver detalle"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {trades.length > 0 && (
          <div className="mt-8 overflow-x-auto">
            <h3 className="text-sm font-bold text-ink">Operaciones de la corrida seleccionada</h3>
            <table className="mt-4 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Lado</th>
                  <th className="pb-2 pr-4 font-medium">Entrada</th>
                  <th className="pb-2 pr-4 font-medium">Precio entrada</th>
                  <th className="pb-2 pr-4 font-medium">Salida</th>
                  <th className="pb-2 pr-4 font-medium">Precio salida</th>
                  <th className="pb-2 font-medium">PnL</th>
                </tr>
              </thead>
              <tbody>
                {trades
                  .slice()
                  .reverse()
                  .map((trade, i) => (
                    <tr key={i} className="border-b border-border last:border-0">
                      <td className="py-2 pr-4 font-semibold uppercase text-ink">{trade.side}</td>
                      <td className="py-2 pr-4 text-ink">
                        {new Date(trade.entry_timestamp).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit" })}
                      </td>
                      <td className="py-2 pr-4 text-ink">
                        {trade.entry_price.toLocaleString("es-AR", { maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-2 pr-4 text-ink">
                        {new Date(trade.exit_timestamp).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit" })}
                      </td>
                      <td className="py-2 pr-4 text-ink">
                        {trade.exit_price.toLocaleString("es-AR", { maximumFractionDigits: 2 })}
                      </td>
                      <td className={`py-2 ${trade.pnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {trade.pnl.toLocaleString("es-AR", { maximumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
