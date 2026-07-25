"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import type { LiveBacktestMetrics } from "@/lib/api";

export interface DatasetOption {
  symbol: string;
  timeframe: string;
  dataset: string;
}

export interface BacktestRunSummary {
  id: number;
  symbol: string;
  timeframe: string;
  dataset: string;
  initial_equity: number;
  num_trades: number;
  metrics: LiveBacktestMetrics;
  created_at: string;
}

export interface SavedStrategySummary {
  id: number;
  name: string;
  strategy_type: string;
  category: string;
  symbols: string[];
  timeframes: string[];
  entry_conditions: string;
  exit_conditions: string;
  config: Record<string, unknown>;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
  latest_run: BacktestRunSummary | null;
}

const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "scalping", label: "Scalping" },
  { value: "day_trading", label: "Day Trading" },
  { value: "swing", label: "Swing" },
];

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(CATEGORY_OPTIONS.map((c) => [c.value, c.label]));

interface FormState {
  name: string;
  category: string;
  symbols: string[];
  timeframes: string[];
  entryConditions: string;
  exitConditions: string;
  notes: string;
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

function defaultsFor(datasets: DatasetOption[]): FormState {
  return {
    name: "",
    category: "swing",
    symbols: datasets.length > 0 ? [datasets[0].symbol] : [],
    timeframes: datasets.length > 0 ? [datasets[0].timeframe] : [],
    entryConditions: "",
    exitConditions: "",
    notes: "",
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

function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
  emptyHint,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
  emptyHint: string;
}) {
  function toggle(value: string) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      {options.length === 0 && <span className="text-xs text-muted">{emptyHint}</span>}
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            type="button"
            key={opt}
            onClick={() => toggle(opt)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
              selected.includes(opt) ? "border-ink bg-ink text-white" : "border-border bg-surface text-muted"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

function buildConfig(form: FormState, symbol: string, timeframe: string) {
  return {
    symbol,
    timeframe,
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

function StatusBadge({ status }: { status: string }) {
  const active = status === "active";
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
        active ? "bg-emerald-100 text-emerald-700" : "bg-surface text-muted"
      }`}
    >
      {active ? "Activa" : "Pausada"}
    </span>
  );
}

export function ConstructorClient({
  initialStrategies,
  initialError,
  catalog,
  datasets,
}: {
  initialStrategies: SavedStrategySummary[];
  initialError: string | null;
  catalog: string[];
  datasets: DatasetOption[];
}) {
  const [strategies, setStrategies] = useState<SavedStrategySummary[]>(initialStrategies);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const [form, setForm] = useState<FormState>(() => defaultsFor(datasets));
  const [showForm, setShowForm] = useState(initialStrategies.length === 0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const availableSymbols = useMemo(() => Array.from(new Set(datasets.map((d) => d.symbol))), [datasets]);
  const availableTimeframes = useMemo(() => Array.from(new Set(datasets.map((d) => d.timeframe))), [datasets]);

  // El primer combo símbolo+timeframe elegido que efectivamente tiene dataset: es lo
  // que se usa para correr el primer backtest al guardar. Si no hay ninguno, no
  // dejamos guardar — evita un 400 confuso del backend por falta de dataset.
  const firstValidCombo = useMemo(
    () => datasets.find((d) => form.symbols.includes(d.symbol) && form.timeframes.includes(d.timeframe)) ?? null,
    [datasets, form.symbols, form.timeframes],
  );

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function reloadStrategies() {
    try {
      const response = await fetch("/api/strategies");
      const data = await response.json();
      if (response.ok) setStrategies(data);
    } catch {
      // silencioso: si falla el refresh, se mantiene el estado anterior
    }
  }

  async function createStrategy() {
    if (!firstValidCombo) return;
    setCreating(true);
    setCreateError(null);

    try {
      const response = await fetch("/api/strategies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          strategy_type: "ma_crossover",
          category: form.category,
          symbols: form.symbols,
          timeframes: form.timeframes,
          entry_conditions: form.entryConditions,
          exit_conditions: form.exitConditions,
          notes: form.notes,
          config: buildConfig(form, firstValidCombo.symbol, firstValidCombo.timeframe),
          initial_equity: form.initialEquity,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setCreateError(typeof data.detail === "string" ? data.detail : "No se pudo guardar la estrategia.");
        return;
      }

      setLoadError(null);
      setShowForm(false);
      setForm(defaultsFor(datasets));
      await reloadStrategies();
    } catch {
      setCreateError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setCreating(false);
    }
  }

  const activeCount = strategies.filter((s) => s.status === "active").length;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Constructor de Estrategias
            <InfoGuide>
              Guardá una estrategia con su nombre, categoría, mercados y temporalidades donde aplica, y los
              parámetros técnicos (EMA, ATR, stop loss, take profit, trailing stop, riesgo por operación).
              Al guardarla corre un primer backtest real automáticamente. Desde el detalle de cada
              estrategia podés volver a correr backtests (eligiendo símbolo y timeframe entre los que
              declaraste) y ver el historial completo de resultados.
              <br />
              <br />
              &quot;Condiciones de entrada/salida&quot; son texto libre: hoy la lógica de la estrategia
              (&quot;{catalog[0] ?? "ma_crossover"}&quot;) es fija en el motor, así que estos campos
              documentan qué hace, no la ejecutan.
              <br />
              <br />
              Los mercados/temporalidades solo pueden ser combinaciones para las que existe un dataset real
              cargado en el servidor — hoy eso limita bastante las opciones, van a ir creciendo.
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">Guardá estrategias y corré backtests reales con historial</p>
        </div>
        <div className="flex items-center gap-3">
          <DataBadge
            live={activeCount > 0}
            label={activeCount > 0 ? `${activeCount} estrategia(s) activa(s)` : "Sin estrategias activas"}
          />
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
          >
            {showForm ? "Cancelar" : "+ Nueva estrategia"}
          </button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus estrategias: </span>
          {loadError}
        </div>
      )}

      {showForm && (
        <div className="rounded-3xl bg-panel p-8">
          <h2 className="text-lg font-bold text-ink">Guardar nueva estrategia</h2>
          <p className="mt-1 text-sm text-muted">Estrategia base: ma_crossover (EMA Crossover)</p>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Nombre</span>
              <input
                type="text"
                value={form.name}
                onChange={(e) => update("name", e.target.value)}
                placeholder="Ej: Mi EMA Crossover conservador"
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Categoría</span>
              <select
                value={form.category}
                onChange={(e) => update("category", e.target.value)}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              >
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <Field label="Equity inicial ($)" value={form.initialEquity} step="100" min="100" onChange={(v) => update("initialEquity", v)} />

            <CheckboxGroup
              label="Mercados"
              options={availableSymbols}
              selected={form.symbols}
              onChange={(v) => update("symbols", v)}
              emptyHint="no hay datasets disponibles todavía"
            />
            <CheckboxGroup
              label="Temporalidades compatibles"
              options={availableTimeframes}
              selected={form.timeframes}
              onChange={(v) => update("timeframes", v)}
              emptyHint="no hay datasets disponibles todavía"
            />
          </div>

          {!firstValidCombo && (form.symbols.length > 0 || form.timeframes.length > 0) && (
            <p className="mt-3 text-xs text-red-600">
              No hay dataset disponible para ninguna combinación de los mercados/temporalidades elegidos.
            </p>
          )}

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Condiciones de entrada</span>
              <textarea
                value={form.entryConditions}
                onChange={(e) => update("entryConditions", e.target.value)}
                rows={2}
                placeholder="Ej: EMA rápida cruza por encima de la lenta con ATR suficiente"
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Condiciones de salida</span>
              <textarea
                value={form.exitConditions}
                onChange={(e) => update("exitConditions", e.target.value)}
                rows={2}
                placeholder="Ej: EMA rápida cruza por debajo de la lenta"
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
          </div>

          <label className="mt-4 flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted">Notas</span>
            <textarea
              value={form.notes}
              onChange={(e) => update("notes", e.target.value)}
              rows={2}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
            />
          </label>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <Field label="EMA rápida (períodos)" value={form.emaFastPeriod} step="1" min="1" onChange={(v) => update("emaFastPeriod", v)} />
            <Field label="EMA lenta (períodos)" value={form.emaSlowPeriod} step="1" min="1" onChange={(v) => update("emaSlowPeriod", v)} />
            <Field label="ATR (períodos)" value={form.atrPeriod} step="1" min="1" onChange={(v) => update("atrPeriod", v)} />
            <Field label="ATR mínimo (%)" value={form.atrMinValuePct} onChange={(v) => update("atrMinValuePct", v)} />
            <Field label="Stop Loss (%)" value={form.stopLossPct} onChange={(v) => update("stopLossPct", v)} />
            <Field label="Take Profit (%)" value={form.takeProfitPct} onChange={(v) => update("takeProfitPct", v)} />
            <Field label="Trailing Stop (%)" value={form.trailingStopPct} onChange={(v) => update("trailingStopPct", v)} />
            <Field label="Riesgo por operación (%)" value={form.riskPerTrade} onChange={(v) => update("riskPerTrade", v)} />
          </div>

          <button
            onClick={createStrategy}
            disabled={creating || !form.name || !firstValidCombo}
            className="mt-6 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {creating ? "Guardando y corriendo backtest…" : "Guardar y correr backtest"}
          </button>

          {createError && (
            <p className="mt-4 text-sm text-muted">
              <span className="font-semibold text-ink">No se pudo guardar: </span>
              {createError}
            </p>
          )}
        </div>
      )}

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Estrategias guardadas</h2>

        {strategies.length === 0 && <p className="mt-4 text-sm text-muted">Todavía no guardaste ninguna estrategia.</p>}

        {strategies.length > 0 && (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Nombre</th>
                  <th className="pb-2 pr-4 font-medium">Categoría</th>
                  <th className="pb-2 pr-4 font-medium">Mercados</th>
                  <th className="pb-2 pr-4 font-medium">Estado</th>
                  <th className="pb-2 pr-4 font-medium">Última corrida</th>
                  <th className="pb-2 pr-4 font-medium">Win rate</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {strategies.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0">
                    <td className="py-3 pr-4 font-semibold text-ink">{s.name}</td>
                    <td className="py-3 pr-4 text-muted">{CATEGORY_LABELS[s.category] ?? s.category}</td>
                    <td className="py-3 pr-4 text-muted">{s.symbols.join(", ")}</td>
                    <td className="py-3 pr-4">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="py-3 pr-4 text-muted">
                      {s.latest_run
                        ? `${s.latest_run.symbol} · ${s.latest_run.timeframe} · ${s.latest_run.num_trades} ops`
                        : "sin corridas"}
                    </td>
                    <td className="py-3 pr-4 text-ink">
                      {s.latest_run ? `${(s.latest_run.metrics.win_rate * 100).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%` : "—"}
                    </td>
                    <td className="py-3">
                      <Link href={`/constructor/${s.id}`} className="text-sm font-semibold text-ink underline">
                        Ver detalle →
                      </Link>
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
