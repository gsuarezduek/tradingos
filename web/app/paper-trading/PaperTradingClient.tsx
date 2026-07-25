"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";

// Pares más operados como sugerencia inicial (antes de escribir); se filtran contra la
// lista real de Binance por si alguno dejara de estar disponible.
const POPULAR_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ETHBTC", "BNBBTC", "BNBETH"];
const MAX_SUGGESTIONS = 30;

export interface SessionSummary {
  id: number;
  strategy: string;
  symbol: string;
  timeframe: string;
  status: string;
  initial_equity: number;
  current_equity: number;
  last_tick_at: string | null;
  created_at: string;
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

function SymbolCombobox({
  value,
  symbols,
  onChange,
}: {
  value: string;
  symbols: string[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const query = value.trim().toUpperCase();
  const suggestions = query
    ? symbols.filter((s) => s.includes(query)).slice(0, MAX_SUGGESTIONS)
    : POPULAR_SYMBOLS.filter((s) => symbols.length === 0 || symbols.includes(s));

  const knownSymbol = symbols.length === 0 || symbols.includes(query);

  return (
    <div ref={containerRef} className="relative flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">Símbolo</span>
      <input
        type="text"
        value={value}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          onChange(e.target.value.toUpperCase());
          setOpen(true);
        }}
        placeholder="Ej: BTCUSDT"
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
      {!knownSymbol && <span className="text-xs text-red-600">no está en la lista de pares de Binance</span>}
      {open && suggestions.length > 0 && (
        <ul className="absolute top-full z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-border bg-surface shadow-lg">
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => {
                  onChange(s);
                  setOpen(false);
                }}
                className="block w-full px-3 py-2 text-left text-sm text-ink hover:bg-panel"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const active = status === "active";
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
        active ? "bg-emerald-100 text-emerald-700" : "bg-surface text-muted"
      }`}
    >
      {active ? "Activa" : "Detenida"}
    </span>
  );
}

export function PaperTradingClient({
  initialSessions,
  initialError,
  symbols,
}: {
  initialSessions: SessionSummary[];
  initialError: string | null;
  symbols: string[];
}) {
  const [sessions, setSessions] = useState<SessionSummary[]>(initialSessions);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const [form, setForm] = useState<FormState>(DEFAULTS);
  const [showForm, setShowForm] = useState(initialSessions.length === 0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function reloadSessions() {
    try {
      const response = await fetch("/api/paper-trading/sessions");
      const data = await response.json();
      if (response.ok) setSessions(data);
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
      setShowForm(false);
      setForm(DEFAULTS);
      await reloadSessions();
    } catch {
      setCreateError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setCreating(false);
    }
  }

  const activeCount = sessions.filter((s) => s.status === "active").length;
  const symbolValid = symbols.length === 0 || symbols.includes(form.symbol.trim().toUpperCase());

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Paper Trading
            <InfoGuide>
              Paper Trading simula la ejecución de una estrategia contra el mercado real en curso, sin
              usar plata real. Cada sesión corre el motor de backtest cada 15 minutos (vía un servicio
              cron) sobre las últimas velas cerradas del símbolo elegido, y actualiza el equity, la
              posición abierta y las operaciones cerradas.
              <br />
              <br />
              El campo Símbolo autocompleta contra la lista real de pares spot de Binance (empezá a
              escribir, ej. &quot;BTC&quot;) — solo se pueden lanzar sesiones sobre pares que Binance
              efectivamente opera.
              <br />
              <br />
              Podés tener varias sesiones corriendo en simultáneo: dale a &quot;+ Nueva sesión&quot; las
              veces que quieras sin necesidad de detener las que ya están activas. Esta pantalla lista
              todas tus sesiones (activas e históricas); hacé clic en &quot;Ver detalle&quot; para ver el
              equity, la posición abierta, los parámetros configurados y las operaciones cerradas de cada
              una, y desde ahí podés detenerla cuando quieras (queda guardada en el historial, no se
              borra).
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">Simulación en vivo sobre el mercado real, sin plata real</p>
        </div>
        <div className="flex items-center gap-3">
          <DataBadge
            live={activeCount > 0}
            label={activeCount > 0 ? `${activeCount} sesión(es) activa(s)` : "Sin sesiones activas"}
          />
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
          >
            {showForm ? "Cancelar" : "+ Nueva sesión"}
          </button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus sesiones: </span>
          {loadError}
        </div>
      )}

      {showForm && (
        <div className="rounded-3xl bg-panel p-8">
          <h2 className="text-lg font-bold text-ink">Iniciar sesión de paper trading</h2>
          <p className="mt-1 text-sm text-muted">EMA Crossover · 1h</p>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <SymbolCombobox value={form.symbol} symbols={symbols} onChange={(v) => update("symbol", v)} />
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
            disabled={creating || !form.symbol || !symbolValid}
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

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Historial de sesiones</h2>

        {sessions.length === 0 && <p className="mt-4 text-sm text-muted">Todavía no iniciaste ninguna sesión.</p>}

        {sessions.length > 0 && (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Símbolo</th>
                  <th className="pb-2 pr-4 font-medium">Estado</th>
                  <th className="pb-2 pr-4 font-medium">Equity inicial</th>
                  <th className="pb-2 pr-4 font-medium">Equity actual</th>
                  <th className="pb-2 pr-4 font-medium">PnL</th>
                  <th className="pb-2 pr-4 font-medium">Iniciada</th>
                  <th className="pb-2 pr-4 font-medium">Última actualización</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => {
                  const pnlPct = ((s.current_equity - s.initial_equity) / s.initial_equity) * 100;
                  return (
                    <tr key={s.id} className="border-b border-border last:border-0">
                      <td className="py-3 pr-4 font-semibold text-ink">
                        {s.symbol} <span className="font-normal text-muted">· {s.strategy}</span>
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="py-3 pr-4 text-ink">${s.initial_equity.toLocaleString("es-AR")}</td>
                      <td className="py-3 pr-4 text-ink">${s.current_equity.toLocaleString("es-AR")}</td>
                      <td className={`py-3 pr-4 font-semibold ${pnlPct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {pnlPct >= 0 ? "+" : ""}
                        {pnlPct.toLocaleString("es-AR", { maximumFractionDigits: 2 })}%
                      </td>
                      <td className="py-3 pr-4 text-muted">
                        {new Date(s.created_at).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="py-3 pr-4 text-muted">
                        {s.last_tick_at
                          ? new Date(s.last_tick_at).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
                          : "todavía no corrió"}
                      </td>
                      <td className="py-3">
                        <Link href={`/paper-trading/${s.id}`} className="text-sm font-semibold text-ink underline">
                          Ver detalle →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
