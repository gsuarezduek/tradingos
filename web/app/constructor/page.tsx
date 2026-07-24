"use client";

import { useState } from "react";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { TopMetricsPanel } from "@/components/TopMetricsPanel";
import type { LiveBacktestMetrics } from "@/lib/api";

interface FormState {
  emaFastPeriod: number;
  emaSlowPeriod: number;
  atrPeriod: number;
  atrMinValuePct: number;
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  riskPerTrade: number;
  initialEquity: number;
}

const DEFAULTS: FormState = {
  emaFastPeriod: 12,
  emaSlowPeriod: 26,
  atrPeriod: 14,
  atrMinValuePct: 0.1,
  stopLossPct: 2,
  takeProfitPct: 4,
  trailingStopPct: 1.5,
  riskPerTrade: 1,
  initialEquity: 10000,
};

interface BacktestResult {
  numTrades: number;
  metrics: LiveBacktestMetrics;
  equityCurve: { timestamp: string; equity: number }[];
}

function Field({
  label,
  value,
  onChange,
  step = "0.1",
  min = "0",
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: string;
  min?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
    </label>
  );
}

export default function ConstructorPage() {
  const [form, setForm] = useState<FormState>(DEFAULTS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);

  function update<K extends keyof FormState>(key: K, value: number) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function runBacktest() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/backtests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          initial_equity: form.initialEquity,
          config: {
            symbol: "BTCUSDT",
            timeframe: "1h",
            stop_loss_pct: form.stopLossPct / 100,
            take_profit_pct: form.takeProfitPct / 100,
            trailing_stop_pct: form.trailingStopPct / 100,
            risk_per_trade: form.riskPerTrade / 100,
            position_sizing: { method: "risk_fraction" },
            indicators: {
              ema_fast: { period: form.emaFastPeriod },
              ema_slow: { period: form.emaSlowPeriod },
              atr: { period: form.atrPeriod, min_value_pct: form.atrMinValuePct / 100 },
            },
          },
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Error al correr el backtest.");
        return;
      }

      setResult({
        numTrades: data.num_trades,
        metrics: data.metrics,
        equityCurve: data.equity_curve,
      });
    } catch {
      setError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? result.equityCurve.slice(-5).map((point) => ({
        label: new Date(point.timestamp).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }),
        value: point.equity,
      }))
    : [];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Constructor de Estrategias
            <InfoGuide>
              Ajustá los parámetros de la estrategia EMA Crossover (medias móviles, ATR, stop loss, take
              profit, trailing stop, riesgo por operación) y corré un backtest real sobre BTCUSDT 1h con el
              botón &quot;Correr backtest&quot;. Hoy el símbolo, el timeframe y el dataset están fijos porque es
              lo único que hay deployado; un backtest real puede tardar varios segundos.
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">EMA Crossover · BTCUSDT · 1h</p>
        </div>
        <DataBadge live={result !== null} label={result ? "Backtest real" : "Configurá y corré"} />
      </div>

      <div className="rounded-3xl bg-panel p-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <Field label="EMA rápida (períodos)" value={form.emaFastPeriod} step="1" min="1" onChange={(v) => update("emaFastPeriod", v)} />
          <Field label="EMA lenta (períodos)" value={form.emaSlowPeriod} step="1" min="1" onChange={(v) => update("emaSlowPeriod", v)} />
          <Field label="ATR (períodos)" value={form.atrPeriod} step="1" min="1" onChange={(v) => update("atrPeriod", v)} />
          <Field label="ATR mínimo (%)" value={form.atrMinValuePct} onChange={(v) => update("atrMinValuePct", v)} />
          <Field label="Stop Loss (%)" value={form.stopLossPct} onChange={(v) => update("stopLossPct", v)} />
          <Field label="Take Profit (%)" value={form.takeProfitPct} onChange={(v) => update("takeProfitPct", v)} />
          <Field label="Trailing Stop (%)" value={form.trailingStopPct} onChange={(v) => update("trailingStopPct", v)} />
          <Field label="Riesgo por operación (%)" value={form.riskPerTrade} onChange={(v) => update("riskPerTrade", v)} />
          <Field label="Equity inicial ($)" value={form.initialEquity} step="100" min="100" onChange={(v) => update("initialEquity", v)} />
        </div>

        <button
          onClick={runBacktest}
          disabled={loading}
          className="mt-6 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Corriendo backtest…" : "Correr backtest"}
        </button>
      </div>

      {error && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo correr el backtest: </span>
          {error}
        </div>
      )}

      {result && (
        <TopMetricsPanel
          chartTitle="Equity semanal"
          chartData={chartData}
          winRatePct={result.metrics.win_rate * 100}
          capitalActual={result.equityCurve.at(-1)?.equity ?? form.initialEquity}
          statLabel="Operaciones cerradas"
          statValue={String(result.numTrades)}
          live
        />
      )}
    </div>
  );
}
