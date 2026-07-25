"use client";

import { useState } from "react";
import { DataBadge } from "@/components/DataBadge";
import { TopMetricsPanel } from "@/components/TopMetricsPanel";

interface OpenPosition {
  side: string;
  entry_price: number;
  quantity: number;
  stop_loss: number | null;
  take_profit: number | null;
  entry_timestamp: string | null;
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

export interface SessionDetail {
  id: number;
  strategy: string;
  symbol: string;
  timeframe: string;
  status: string;
  initial_equity: number;
  current_equity: number;
  open_position: OpenPosition | null;
  last_tick_at: string | null;
  created_at: string;
  equity_curve: { timestamp: string; equity: number }[];
  trades: Trade[];
}

interface FormState {
  symbol: string;
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
  symbol: "BTCUSDT",
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

function buildConfig(form: FormState) {
  return {
    symbol: form.symbol,
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
  };
}

export function PaperTradingClient({
  initialSession,
  initialError,
}: {
  initialSession: SessionDetail | null;
  initialError: string | null;
}) {
  const [session, setSession] = useState<SessionDetail | null>(initialSession);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const [form, setForm] = useState<FormState>(DEFAULTS);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function reloadSession(sessionId: number) {
    try {
      const response = await fetch(`/api/paper-trading/sessions/${sessionId}`);
      const data = await response.json();
      if (response.ok) setSession(data);
    } catch {
      // silencioso: si falla el refresh, se mantiene el estado anterior
    }
  }

  async function createSession() {
    setCreating(true);
    setCreateError(null);

    try {
      const response = await fetch("/api/paper-trading/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: buildConfig(form), initial_equity: form.initialEquity }),
      });
      const data = await response.json();
      if (!response.ok) {
        setCreateError(typeof data.detail === "string" ? data.detail : "No se pudo iniciar la sesión.");
        return;
      }

      setLoadError(null);
      await reloadSession(data.id);
    } catch {
      setCreateError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setCreating(false);
    }
  }

  async function stopSession() {
    if (!session) return;
    setStopping(true);
    try {
      await fetch(`/api/paper-trading/sessions/${session.id}/stop`, { method: "POST" });
      await reloadSession(session.id);
    } finally {
      setStopping(false);
    }
  }

  const isActive = session?.status === "active";
  const trades = session?.trades ?? [];
  const winRatePct = trades.length > 0 ? (trades.filter((t) => t.pnl > 0).length / trades.length) * 100 : 0;
  const chartData =
    session?.equity_curve.slice(-5).map((point) => ({
      label: new Date(point.timestamp).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit" }),
      value: point.equity,
    })) ?? [];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Paper Trading</h1>
          <p className="text-sm text-muted">Simulación en vivo sobre el mercado real, sin plata real</p>
        </div>
        <DataBadge live={isActive} label={isActive ? "Sesión activa" : "Sin sesión activa"} />
      </div>

      {loadError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus sesiones: </span>
          {loadError}
        </div>
      )}

      {!isActive && (
        <div className="rounded-3xl bg-panel p-8">
          <h2 className="text-lg font-bold text-ink">Iniciar sesión de paper trading</h2>
          <p className="mt-1 text-sm text-muted">EMA Crossover · 1h · una sesión activa a la vez</p>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Símbolo</span>
              <input
                type="text"
                value={form.symbol}
                onChange={(e) => update("symbol", e.target.value.toUpperCase())}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
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
            onClick={createSession}
            disabled={creating || !form.symbol}
            className="mt-6 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {creating ? "Iniciando…" : "Iniciar paper trading"}
          </button>

          {createError && (
            <p className="mt-4 text-sm text-muted">
              <span className="font-semibold text-ink">No se pudo iniciar: </span>
              {createError}
            </p>
          )}
        </div>
      )}

      {session && (
        <>
          <TopMetricsPanel
            chartTitle="Equity reciente"
            chartData={chartData}
            winRatePct={winRatePct}
            capitalActual={session.current_equity}
            statLabel="Operaciones cerradas"
            statValue={String(trades.length)}
            live={isActive}
          />

          <div className="rounded-3xl bg-panel p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-ink">
                  {session.symbol} · {session.strategy}
                </h2>
                <p className="text-xs text-muted">
                  {isActive ? "Activa" : "Detenida"} · Última actualización:{" "}
                  {session.last_tick_at ? new Date(session.last_tick_at).toLocaleString("es-AR") : "todavía no corrió ningún tick"}
                </p>
              </div>
              {isActive && (
                <button
                  onClick={stopSession}
                  disabled={stopping}
                  className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted disabled:opacity-50"
                >
                  {stopping ? "Deteniendo…" : "Detener"}
                </button>
              )}
            </div>

            {session.open_position && (
              <div className="mt-6 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-ink">
                <span className="font-semibold uppercase">{session.open_position.side}</span> abierta @{" "}
                {session.open_position.entry_price.toLocaleString("es-AR", { maximumFractionDigits: 2 })} · qty{" "}
                {session.open_position.quantity.toLocaleString("es-AR", { maximumFractionDigits: 6 })}
              </div>
            )}

            {trades.length === 0 && <p className="mt-6 text-sm text-muted">Todavía no se cerró ninguna operación.</p>}

            {trades.length > 0 && (
              <div className="mt-6 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                      <th className="pb-2 pr-4 font-medium">Lado</th>
                      <th className="pb-2 pr-4 font-medium">Entrada</th>
                      <th className="pb-2 pr-4 font-medium">Salida</th>
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
                            {new Date(trade.exit_timestamp).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit" })}
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
        </>
      )}
    </div>
  );
}
