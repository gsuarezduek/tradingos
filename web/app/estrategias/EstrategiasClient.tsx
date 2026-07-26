"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import type { LiveBacktestMetrics } from "@/lib/api";

// Pares más operados como sugerencia inicial (antes de escribir); mismo criterio que el
// combobox de símbolo de Paper Trading.
const POPULAR_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ETHBTC", "BNBBTC", "BNBETH"];
const MAX_SUGGESTIONS = 30;

// Temporalidades ofrecidas en el formulario. El motor sabe anualizar métricas para
// todas estas (ver SUPPORTED_TIMEFRAMES en backtest/engine.py) — que aparezcan acá no
// implica que ya exista un dataset real para correr un backtest en esa temporalidad.
export const TIMEFRAME_OPTIONS = ["3m", "5m", "30m", "1h", "4h", "1d", "1w"];

export interface Condition {
  category: string;
  condition_type: string;
  params: Record<string, number>;
}

export interface ConditionTypeOption {
  type: string;
  label: string;
  params: string[];
}

export interface ConditionCategory {
  category: string;
  label: string;
  available: boolean;
  condition_types: ConditionTypeOption[];
}

const PARAM_LABELS: Record<string, string> = {
  period: "Período",
  period_a: "Período rápido",
  period_b: "Período lento",
  lookback: "Velas atrás",
  threshold_pct: "Umbral (%)",
};

const PARAM_DEFAULTS: Record<string, number> = {
  period: 20,
  period_a: 12,
  period_b: 26,
  lookback: 5,
  threshold_pct: 1,
};

export interface DatasetOption {
  symbol: string;
  timeframe: string;
  dataset: string;
  start: string;
  end: string;
}

export interface BacktestRunSummary {
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

export const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "scalping", label: "Scalping" },
  { value: "day_trading", label: "Day Trading" },
  { value: "swing", label: "Swing" },
];

export const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(CATEGORY_OPTIONS.map((c) => [c.value, c.label]));

// El equity inicial ya no se pide acá: se define al correr cada backtest (ver
// StrategyDetailClient), así que el primer backtest automático al guardar parte de
// este default fijo.
const DEFAULT_INITIAL_EQUITY = 10_000;

export interface FormState {
  name: string;
  category: string;
  symbols: string[];
  timeframes: string[];
  // Lista de grupos: O entre grupos, Y dentro de cada uno. Un solo grupo con varias
  // condiciones es el caso de siempre ("todas deben cumplirse"); agregar un segundo
  // grupo es lo que habilita "esto O aquello".
  entryRules: Condition[][];
  exitRules: Condition[][];
  notes: string;
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  riskPerTrade: number;
}

export function defaultsFor(datasets: DatasetOption[]): FormState {
  return {
    name: "",
    category: "swing",
    symbols: datasets.length > 0 ? [datasets[0].symbol] : [],
    timeframes: datasets.length > 0 ? [datasets[0].timeframe] : [],
    entryRules: [],
    exitRules: [],
    notes: "",
    stopLossPct: 2,
    takeProfitPct: 4,
    trailingStopPct: 1.5,
    riskPerTrade: 1,
  };
}

export function Field({
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

export function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
  emptyHint = "",
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
  emptyHint?: string;
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

export function MultiSymbolCombobox({
  label,
  selected,
  symbols,
  onChange,
}: {
  label: string;
  selected: string[];
  symbols: string[];
  onChange: (values: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const normalizedQuery = query.trim().toUpperCase();
  const suggestions = (
    normalizedQuery ? symbols.filter((s) => s.includes(normalizedQuery)) : POPULAR_SYMBOLS.filter((s) => symbols.length === 0 || symbols.includes(s))
  )
    .filter((s) => !selected.includes(s))
    .slice(0, MAX_SUGGESTIONS);

  function addSymbol(symbol: string) {
    if (!selected.includes(symbol)) onChange([...selected, symbol]);
    setQuery("");
    setOpen(false);
  }

  function removeSymbol(symbol: string) {
    onChange(selected.filter((s) => s !== symbol));
  }

  return (
    <div ref={containerRef} className="relative flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((s) => (
            <button
              type="button"
              key={s}
              onClick={() => removeSymbol(s)}
              className="rounded-lg border border-ink bg-ink px-3 py-1.5 text-xs font-semibold text-white"
            >
              {s} ✕
            </button>
          ))}
        </div>
      )}
      <input
        type="text"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value.toUpperCase());
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && normalizedQuery) {
            e.preventDefault();
            addSymbol(normalizedQuery);
          }
        }}
        placeholder="Agregar par, ej: ETHUSDT"
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
      {open && suggestions.length > 0 && (
        <ul className="absolute top-full z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-border bg-surface shadow-lg">
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => addSymbol(s)}
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

function paramsKey(params: Record<string, number>): string {
  return Object.keys(params)
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join(",");
}

function conditionsEqual(a: Condition, b: Condition): boolean {
  return a.category === b.category && a.condition_type === b.condition_type && paramsKey(a.params) === paramsKey(b.params);
}

export function conditionLabel(catalog: ConditionCategory[], condition: Condition): string {
  const conditionType = catalog
    .find((c) => c.category === condition.category)
    ?.condition_types.find((t) => t.type === condition.condition_type);
  const paramsText = Object.entries(condition.params)
    .map(([key, value]) => `${PARAM_LABELS[key] ?? key}=${value}`)
    .join(", ");
  return `${conditionType?.label ?? condition.condition_type}${paramsText ? ` (${paramsText})` : ""}`;
}

// null = ningún panel abierto; "new" = agregando un grupo nuevo (O); number = agregando
// una condición (Y) al grupo en ese índice.
type AddTarget = number | "new" | null;

export function ConditionBuilder({
  label,
  groups,
  onChange,
  catalog,
  emptyHint,
}: {
  label: string;
  groups: Condition[][];
  onChange: (groups: Condition[][]) => void;
  catalog: ConditionCategory[];
  emptyHint: string;
}) {
  const firstAvailable = catalog.find((c) => c.available) ?? catalog[0];
  const [target, setTarget] = useState<AddTarget>(null);
  const [category, setCategory] = useState(firstAvailable?.category ?? "");
  const [conditionType, setConditionType] = useState(firstAvailable?.condition_types[0]?.type ?? "");
  const [params, setParams] = useState<Record<string, number>>({});
  const [duplicateWarning, setDuplicateWarning] = useState(false);

  const selectedCategory = catalog.find((c) => c.category === category);
  const selectedType = selectedCategory?.condition_types.find((t) => t.type === conditionType);

  function selectConditionType(category: ConditionCategory, type: ConditionTypeOption) {
    setCategory(category.category);
    setConditionType(type.type);
    setParams(Object.fromEntries(type.params.map((p) => [p, PARAM_DEFAULTS[p] ?? 1])));
    setDuplicateWarning(false);
  }

  function startAdding(nextTarget: AddTarget) {
    if (firstAvailable?.condition_types[0]) selectConditionType(firstAvailable, firstAvailable.condition_types[0]);
    setTarget(nextTarget);
  }

  function confirmAdd() {
    if (!selectedCategory?.available || !selectedType || target === null) return;
    const condition: Condition = { category, condition_type: conditionType, params };
    const targetGroup = target === "new" ? [] : groups[target];
    if (targetGroup.some((c) => conditionsEqual(c, condition))) {
      setDuplicateWarning(true);
      return;
    }
    if (target === "new") {
      onChange([...groups, [condition]]);
    } else {
      onChange(groups.map((group, i) => (i === target ? [...group, condition] : group)));
    }
    setTarget(null);
    setDuplicateWarning(false);
  }

  function removeCondition(groupIndex: number, conditionIndex: number) {
    const nextGroup = groups[groupIndex].filter((_, i) => i !== conditionIndex);
    // Un grupo sin condiciones no significa nada — desaparece con su última condición.
    onChange(nextGroup.length === 0 ? groups.filter((_, i) => i !== groupIndex) : groups.map((g, i) => (i === groupIndex ? nextGroup : g)));
  }

  function removeGroup(groupIndex: number) {
    onChange(groups.filter((_, i) => i !== groupIndex));
  }

  const addPanel = (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap gap-2">
        {catalog.map((cat) => (
          <button
            type="button"
            key={cat.category}
            disabled={!cat.available}
            onClick={() => cat.condition_types[0] && selectConditionType(cat, cat.condition_types[0])}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold ${
              !cat.available
                ? "cursor-not-allowed border-border text-muted opacity-60"
                : category === cat.category
                  ? "border-ink bg-ink text-white"
                  : "border-border bg-surface text-ink"
            }`}
          >
            {cat.label}
            {!cat.available && (
              <span className="rounded-full border border-border px-1.5 py-0.5 text-[10px]">Próximamente</span>
            )}
          </button>
        ))}
      </div>

      {selectedCategory?.available && (
        <>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted">Tipo de condición</span>
            <select
              value={conditionType}
              onChange={(e) => {
                const type = selectedCategory.condition_types.find((t) => t.type === e.target.value);
                if (type) selectConditionType(selectedCategory, type);
              }}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
            >
              {selectedCategory.condition_types.map((t) => (
                <option key={t.type} value={t.type}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          {selectedType && selectedType.params.length > 0 && (
            <div className="flex flex-wrap gap-3">
              {selectedType.params.map((p) => (
                <label key={p} className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted">{PARAM_LABELS[p] ?? p}</span>
                  <input
                    type="number"
                    min={p === "threshold_pct" ? "0.1" : "1"}
                    step={p === "threshold_pct" ? "0.1" : "1"}
                    value={params[p] ?? ""}
                    onChange={(e) => {
                      setParams((prev) => ({ ...prev, [p]: Number(e.target.value) }));
                      setDuplicateWarning(false);
                    }}
                    className="w-28 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
                  />
                </label>
              ))}
            </div>
          )}

          {duplicateWarning && (
            <p className="text-xs font-semibold text-red-600">Ya agregaste esta misma condición en este grupo.</p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirmAdd}
              disabled={!selectedType}
              className="w-fit rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            >
              Agregar
            </button>
            <button
              type="button"
              onClick={() => {
                setTarget(null);
                setDuplicateWarning(false);
              }}
              className="w-fit rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-muted"
            >
              Cancelar
            </button>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium text-muted">{label}</span>
      {groups.length === 0 && <span className="text-xs text-muted">{emptyHint}</span>}

      <div className="flex flex-col gap-2">
        {groups.map((group, gi) => (
          <div key={gi} className="flex flex-col gap-2">
            {gi > 0 && <div className="text-center text-[10px] font-bold uppercase tracking-wide text-muted">O</div>}
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border p-3">
              {group.map((c, ci) => (
                <div key={ci} className="flex items-center gap-2">
                  {ci > 0 && <span className="text-[10px] font-bold uppercase text-muted">Y</span>}
                  <button
                    type="button"
                    onClick={() => removeCondition(gi, ci)}
                    className="rounded-lg border border-ink bg-ink px-3 py-1.5 text-xs font-semibold text-white"
                  >
                    {conditionLabel(catalog, c)} ✕
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => startAdding(gi)}
                className="rounded-lg border border-dashed border-border px-2 py-1.5 text-xs font-semibold text-muted"
              >
                + Y
              </button>
              <button type="button" onClick={() => removeGroup(gi)} className="ml-1 text-xs font-semibold text-red-600 underline">
                Eliminar grupo
              </button>
            </div>
            {target === gi && addPanel}
          </div>
        ))}
      </div>

      {target !== "new" && (
        <button
          type="button"
          onClick={() => startAdding("new")}
          className="w-fit rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-ink"
        >
          {groups.length === 0 ? "+ Agregar condición" : "+ Agregar grupo (O)"}
        </button>
      )}

      {target === "new" && addPanel}
    </div>
  );
}

export function buildConfig(form: FormState, symbol: string, timeframe: string) {
  return {
    symbol,
    timeframe,
    stop_loss_pct: form.stopLossPct / 100,
    take_profit_pct: form.takeProfitPct / 100,
    trailing_stop_pct: form.trailingStopPct / 100,
    risk_per_trade: form.riskPerTrade / 100,
    position_sizing: { method: "risk_fraction" },
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

export function EstrategiasClient({
  initialStrategies,
  initialError,
  datasets,
  symbols,
  conditionCatalog,
}: {
  initialStrategies: SavedStrategySummary[];
  initialError: string | null;
  datasets: DatasetOption[];
  symbols: string[];
  conditionCatalog: ConditionCategory[];
}) {
  const [strategies, setStrategies] = useState<SavedStrategySummary[]>(initialStrategies);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const [form, setForm] = useState<FormState>(() => defaultsFor(datasets));
  const [showForm, setShowForm] = useState(initialStrategies.length === 0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

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
    if (!firstValidCombo || form.entryRules.length === 0) return;
    setCreating(true);
    setCreateError(null);

    try {
      const response = await fetch("/api/strategies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          strategy_type: "condition_based",
          category: form.category,
          symbols: form.symbols,
          timeframes: form.timeframes,
          entry_rules: form.entryRules,
          exit_rules: form.exitRules,
          notes: form.notes,
          config: buildConfig(form, firstValidCombo.symbol, firstValidCombo.timeframe),
          initial_equity: DEFAULT_INITIAL_EQUITY,
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
            Estrategias
            <InfoGuide>
              Guardá una estrategia con su nombre, categoría, mercados y temporalidades donde aplica, y armá
              sus condiciones de entrada y salida con &quot;+ Agregar condición&quot;: elegí un indicador y un
              tipo de condición (ej. &quot;EMA20 cruza EMA50 hacia arriba&quot;) y sumá todas las que
              necesites dentro de un mismo grupo — ahí todas deben cumplirse (Y). Con &quot;+ Agregar grupo
              (O)&quot; sumás una alternativa: entra (o sale) si CUALQUIER grupo se cumple entero, no hace
              falta que se cumplan todos — por ejemplo &quot;(EMA20 cruza EMA50 hacia arriba Y RSI &lt; 50) O
              (ADX &gt; 25 Y DI+ &gt; DI-)&quot;. Si no agregás ninguna condición de salida, la posición solo se
              cierra por Stop Loss/Take Profit/Trailing Stop.
              <br />
              <br />
              Al guardar corre un primer backtest real automáticamente. Desde el detalle de cada estrategia
              podés volver a correr backtests (eligiendo símbolo, timeframe y rango de fechas) y ver el
              historial completo de resultados.
              <br />
              <br />
              El campo Mercados autocompleta contra la lista real de pares spot de Binance (igual que en
              Paper Trading) — declará ahí todos los que la estrategia podría operar. Eso sí, correr un
              backtest real todavía requiere que exista un dataset cargado para ese símbolo+timeframe
              puntual; si elegís una combinación sin dataset, te avisamos antes de guardar.
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
          <p className="mt-1 text-sm text-muted">Condiciones de entrada y salida</p>

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
            <MultiSymbolCombobox
              label="Mercados"
              symbols={symbols}
              selected={form.symbols}
              onChange={(v) => update("symbols", v)}
            />
            <CheckboxGroup
              label="Temporalidades compatibles"
              options={TIMEFRAME_OPTIONS}
              selected={form.timeframes}
              onChange={(v) => update("timeframes", v)}
            />
          </div>

          {!firstValidCombo && (form.symbols.length > 0 || form.timeframes.length > 0) && (
            <p className="mt-3 text-xs text-red-600">
              No hay dataset disponible para ninguna combinación de los mercados/temporalidades elegidos.
            </p>
          )}

          <div className="mt-4 grid grid-cols-1 gap-6 sm:grid-cols-2">
            <ConditionBuilder
              label="Condiciones de entrada (Y dentro de un grupo, O entre grupos)"
              groups={form.entryRules}
              onChange={(v) => update("entryRules", v)}
              catalog={conditionCatalog}
              emptyHint="Sin condiciones — agregá al menos una para poder guardar"
            />
            <ConditionBuilder
              label="Condiciones de salida (Y dentro de un grupo, O entre grupos)"
              groups={form.exitRules}
              onChange={(v) => update("exitRules", v)}
              catalog={conditionCatalog}
              emptyHint="Sin condiciones — sale solo por Stop Loss/Take Profit/Trailing Stop"
            />
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
            <Field label="Stop Loss (%)" value={form.stopLossPct} onChange={(v) => update("stopLossPct", v)} />
            <Field label="Take Profit (%)" value={form.takeProfitPct} onChange={(v) => update("takeProfitPct", v)} />
            <Field label="Trailing Stop (%)" value={form.trailingStopPct} onChange={(v) => update("trailingStopPct", v)} />
            <Field label="Riesgo por operación (%)" value={form.riskPerTrade} onChange={(v) => update("riskPerTrade", v)} />
          </div>

          <button
            onClick={createStrategy}
            disabled={creating || !form.name || !firstValidCombo || form.entryRules.length === 0}
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
                      <Link href={`/estrategias/${s.id}`} className="text-sm font-semibold text-ink underline">
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
