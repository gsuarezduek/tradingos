"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { TopMetricsPanel } from "@/components/TopMetricsPanel";
import type { LiveBacktestMetrics } from "@/lib/api";
import {
  CATEGORY_OPTIONS,
  CheckboxGroup,
  ConditionBuilder,
  Field,
  MultiSymbolCombobox,
  TIMEFRAME_OPTIONS,
  buildConfig,
  conditionLabel,
  type Condition,
  type ConditionCategory,
  type DatasetOption,
  type FormState,
} from "../EstrategiasClient";

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

export interface LinkedLiveSession {
  id: number;
  strategy_id: number;
  status: string;
  symbol: string;
  exchange: string;
  broker_connection_label: string;
}

export interface LinkedPaperSession {
  id: number;
  strategy_id: number | null;
  status: string;
  symbol: string;
  timeframe: string;
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
  // Siempre en la forma de grupos (O entre grupos, Y dentro de cada uno) — el backend
  // normaliza acá incluso las estrategias guardadas antes de que existieran los grupos.
  entry_rules: Condition[][];
  exit_rules: Condition[][];
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
  symbols,
  initialLiveSessions,
  initialPaperSessions,
}: {
  strategyId: string;
  initialStrategy: StrategyDetail | null;
  initialError: string | null;
  datasets: DatasetOption[];
  conditionCatalog: ConditionCategory[];
  symbols: string[];
  initialLiveSessions: LinkedLiveSession[];
  initialPaperSessions: LinkedPaperSession[];
}) {
  const router = useRouter();
  const [strategy, setStrategy] = useState<StrategyDetail | null>(initialStrategy);
  const [loadError] = useState<string | null>(initialError);
  const [togglingStatus, setTogglingStatus] = useState(false);
  const [liveSessions, setLiveSessions] = useState<LinkedLiveSession[]>(initialLiveSessions);
  const [paperSessions, setPaperSessions] = useState<LinkedPaperSession[]>(initialPaperSessions);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<FormState | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingRunId, setDeletingRunId] = useState<number | null>(null);

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

  async function reloadSessions() {
    const strategyIdNum = Number(strategyId);
    try {
      const [liveResponse, paperResponse] = await Promise.all([
        fetch("/api/live-trading/sessions"),
        fetch("/api/paper-trading/sessions"),
      ]);
      const [liveData, paperData]: [LinkedLiveSession[], LinkedPaperSession[]] = await Promise.all([
        liveResponse.json(),
        paperResponse.json(),
      ]);
      if (liveResponse.ok) setLiveSessions(liveData.filter((s) => s.strategy_id === strategyIdNum));
      if (paperResponse.ok) setPaperSessions(paperData.filter((s) => s.strategy_id === strategyIdNum));
    } catch {
      // silencioso: si falla el refresh, se mantiene el estado anterior
    }
  }

  async function toggleStatus() {
    if (!strategy) return;
    const pausing = strategy.status === "active";

    if (pausing) {
      const activeLive = liveSessions.filter((s) => s.status === "active").length;
      const activePaper = paperSessions.filter((s) => s.status === "active").length;
      if (activeLive > 0 || activePaper > 0) {
        const parts: string[] = [];
        if (activeLive > 0) parts.push(`${activeLive} sesión(es) de Trading Automático`);
        if (activePaper > 0) parts.push(`${activePaper} sesión(es) de Paper Trading`);
        const confirmed = window.confirm(
          `Esta estrategia tiene ${parts.join(" y ")} activa(s). Al pausarla se van a detener automáticamente ` +
            `(no cierra sola ninguna posición real ya abierta — eso seguís teniendo que hacerlo vos desde Operar ` +
            `Manual si hace falta). ¿Confirmar?`,
        );
        if (!confirmed) return;
      }
    }

    setTogglingStatus(true);
    try {
      const nextStatus = pausing ? "paused" : "active";
      await fetch(`/api/strategies/${strategy.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      await reloadStrategy();
      await reloadSessions();
    } finally {
      setTogglingStatus(false);
    }
  }

  function startEditing() {
    if (!strategy) return;
    setEditForm({
      name: strategy.name,
      category: strategy.category,
      symbols: strategy.symbols,
      timeframes: strategy.timeframes,
      entryRules: strategy.entry_rules,
      exitRules: strategy.exit_rules,
      notes: strategy.notes,
      stopLossPct: (strategy.config.stop_loss_pct ?? 0) * 100,
      takeProfitPct: (strategy.config.take_profit_pct ?? 0) * 100,
      trailingStopPct: (strategy.config.trailing_stop_pct ?? 0) * 100,
      riskPerTrade: (strategy.config.risk_per_trade ?? 0) * 100,
    });
    setEditError(null);
    setEditing(true);
  }

  function updateEditForm<K extends keyof FormState>(key: K, value: FormState[K]) {
    setEditForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function saveEdit() {
    if (!strategy || !editForm) return;
    if (editForm.name.trim() === "") {
      setEditError("El nombre no puede estar vacío.");
      return;
    }
    if (strategy.strategy_type === "condition_based" && editForm.entryRules.length === 0) {
      setEditError("Agregá al menos una condición de entrada.");
      return;
    }
    const firstValidEditCombo = datasets.find(
      (d) => editForm.symbols.includes(d.symbol) && editForm.timeframes.includes(d.timeframe),
    );
    if (!firstValidEditCombo) {
      setEditError("No hay dataset disponible para ninguna combinación de los mercados/temporalidades elegidos.");
      return;
    }

    setSavingEdit(true);
    setEditError(null);
    try {
      const response = await fetch(`/api/strategies/${strategy.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editForm.name,
          category: editForm.category,
          symbols: editForm.symbols,
          timeframes: editForm.timeframes,
          entry_rules: editForm.entryRules,
          exit_rules: editForm.exitRules,
          notes: editForm.notes,
          config: buildConfig(editForm, firstValidEditCombo.symbol, firstValidEditCombo.timeframe),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setEditError(typeof data.detail === "string" ? data.detail : "No se pudieron guardar los cambios.");
        return;
      }
      setEditing(false);
      await reloadStrategy();
    } catch {
      setEditError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setSavingEdit(false);
    }
  }

  async function deleteStrategy() {
    if (!strategy) return;
    let message = `¿Eliminar la estrategia "${strategy.name}"? Esta acción no se puede deshacer.`;
    if (paperSessions.length > 0) {
      message += ` Sus ${paperSessions.length} sesión(es) de Paper Trading van a quedar sin estrategia vinculada (conservan su historial).`;
    }
    if (!window.confirm(message)) return;

    setDeleting(true);
    setDeleteError(null);
    try {
      const response = await fetch(`/api/strategies/${strategy.id}`, { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}) as Record<string, unknown>);
        setDeleteError(typeof data.detail === "string" ? data.detail : "No se pudo eliminar la estrategia.");
        setDeleting(false);
        return;
      }
      router.push("/estrategias");
      router.refresh();
    } catch {
      setDeleteError("No se pudo conectar con la API. Probá de nuevo.");
      setDeleting(false);
    }
  }

  async function deleteRun(runId: number) {
    if (!strategy) return;
    if (!window.confirm("¿Eliminar esta corrida del historial? Esta acción no se puede deshacer.")) return;

    setDeletingRunId(runId);
    try {
      const response = await fetch(`/api/strategies/${strategy.id}/backtests/${runId}`, { method: "DELETE" });
      if (response.ok) {
        if (selectedRunId === runId) {
          setSelectedRunId(null);
          setSelectedRunDetail(null);
        }
        await reloadStrategy();
      }
    } finally {
      setDeletingRunId(null);
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
        <Link href="/estrategias" className="text-sm font-semibold text-ink underline">
          ← Volver a Estrategias
        </Link>
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo cargar la estrategia: </span>
          {loadError ?? "estrategia no encontrada"}
        </div>
      </div>
    );
  }

  const isActive = strategy.status === "active";
  const activeSessionsCount =
    liveSessions.filter((s) => s.status === "active").length + paperSessions.filter((s) => s.status === "active").length;
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
      <Link href="/estrategias" className="text-sm font-semibold text-ink underline">
        ← Volver a Estrategias
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
              <br />
              <br />
              &quot;Pausar&quot; ahora sí frena de verdad: si esta estrategia tiene sesiones de Trading Automático
              o Paper Trading activas, se detienen automáticamente (te avisamos antes de confirmar, y no cierra
              sola ninguna posición real ya abierta). Mientras esté pausada tampoco se puede crear una sesión
              nueva con ella. Reactivarla no revive las sesiones que se frenaron — hay que crearlas de nuevo.
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
          {strategy.strategy_type === "condition_based" && (
            <button
              onClick={() => (editing ? setEditing(false) : startEditing())}
              className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted"
            >
              {editing ? "Cancelar edición" : "Editar"}
            </button>
          )}
          <button
            onClick={deleteStrategy}
            disabled={deleting}
            className="rounded-xl border border-red-200 px-4 py-2 text-sm font-semibold text-red-600 disabled:opacity-50"
          >
            {deleting ? "Eliminando…" : "Eliminar"}
          </button>
        </div>
      </div>

      {deleteError && (
        <div className="rounded-3xl bg-panel p-4 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo eliminar: </span>
          {deleteError}
        </div>
      )}

      {(liveSessions.length > 0 || paperSessions.length > 0) && (
        <div className="rounded-3xl bg-panel p-8">
          <h2 className="text-lg font-bold text-ink">Sesiones vinculadas</h2>
          <p className="mt-1 text-sm text-muted">
            Trading Automático y Paper Trading que usan esta estrategia. Pausarla detiene automáticamente las que
            estén activas; eliminarla está bloqueado mientras tenga sesiones de Trading Automático.
          </p>
          <div className="mt-4 flex flex-col gap-2">
            {liveSessions.map((s) => (
              <div key={`live-${s.id}`} className="flex items-center justify-between rounded-xl border border-border px-4 py-2 text-sm">
                <span className="text-ink">
                  <span className="font-semibold">Trading Automático</span> · {s.symbol} ·{" "}
                  <span className="text-muted">{s.broker_connection_label}</span>
                </span>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      s.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-surface text-muted"
                    }`}
                  >
                    {s.status === "active" ? "Activa" : "Detenida"}
                  </span>
                  <Link href={`/trading-automatico/${s.id}`} className="font-semibold text-ink underline">
                    Ver →
                  </Link>
                </div>
              </div>
            ))}
            {paperSessions.map((s) => (
              <div key={`paper-${s.id}`} className="flex items-center justify-between rounded-xl border border-border px-4 py-2 text-sm">
                <span className="text-ink">
                  <span className="font-semibold">Paper Trading</span> · {s.symbol} · {s.timeframe}
                </span>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      s.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-surface text-muted"
                    }`}
                  >
                    {s.status === "active" ? "Activa" : "Detenida"}
                  </span>
                  <Link href={`/paper-trading/${s.id}`} className="font-semibold text-ink underline">
                    Ver →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
        <h2 className="text-lg font-bold text-ink">{editing ? "Editar estrategia" : "Definición de la estrategia"}</h2>

        {editing && editForm && activeSessionsCount > 0 && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <span className="font-semibold">Ojo: </span>
            esta estrategia tiene {activeSessionsCount} sesión(es) activa(s) (Trading Automático y/o Paper Trading).
            Lo que guardes acá <strong>no se aplica</strong> a esas sesiones ya corriendo — cada una toma una foto
            de la configuración al crearse y sigue operando con esa foto hasta que la pares y crees una nueva. Si
            necesitás que el cambio aplique ya, pausá la estrategia (arriba) y activá una sesión nueva después.
          </div>
        )}

        {editing && editForm ? (
          <>
            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted">Nombre</span>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => updateEditForm("name", e.target.value)}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted">Categoría</span>
                <select
                  value={editForm.category}
                  onChange={(e) => updateEditForm("category", e.target.value)}
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
                selected={editForm.symbols}
                onChange={(v) => updateEditForm("symbols", v)}
              />
              <CheckboxGroup
                label="Temporalidades compatibles"
                options={TIMEFRAME_OPTIONS}
                selected={editForm.timeframes}
                onChange={(v) => updateEditForm("timeframes", v)}
              />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-6 sm:grid-cols-2">
              <ConditionBuilder
                label="Condiciones de entrada (Y dentro de un grupo, O entre grupos)"
                groups={editForm.entryRules}
                onChange={(v) => updateEditForm("entryRules", v)}
                catalog={conditionCatalog}
                emptyHint="Sin condiciones — agregá al menos una para poder guardar"
              />
              <ConditionBuilder
                label="Condiciones de salida (Y dentro de un grupo, O entre grupos)"
                groups={editForm.exitRules}
                onChange={(v) => updateEditForm("exitRules", v)}
                catalog={conditionCatalog}
                emptyHint="Sin condiciones — sale solo por Stop Loss/Take Profit/Trailing Stop"
              />
            </div>

            <label className="mt-4 flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Notas</span>
              <textarea
                value={editForm.notes}
                onChange={(e) => updateEditForm("notes", e.target.value)}
                rows={2}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <Field label="Stop Loss (%)" value={editForm.stopLossPct} onChange={(v) => updateEditForm("stopLossPct", v)} />
              <Field label="Take Profit (%)" value={editForm.takeProfitPct} onChange={(v) => updateEditForm("takeProfitPct", v)} />
              <Field label="Trailing Stop (%)" value={editForm.trailingStopPct} onChange={(v) => updateEditForm("trailingStopPct", v)} />
              <Field label="Riesgo por operación (%)" value={editForm.riskPerTrade} onChange={(v) => updateEditForm("riskPerTrade", v)} />
            </div>

            <div className="mt-6 flex items-center gap-3">
              <button
                onClick={saveEdit}
                disabled={savingEdit}
                className="rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {savingEdit ? "Guardando…" : "Guardar cambios"}
              </button>
              <button
                onClick={() => setEditing(false)}
                disabled={savingEdit}
                className="rounded-xl border border-border px-5 py-2.5 text-sm font-semibold text-muted disabled:opacity-50"
              >
                Cancelar
              </button>
            </div>

            {editError && (
              <p className="mt-4 text-sm text-muted">
                <span className="font-semibold text-ink">No se pudo guardar: </span>
                {editError}
              </p>
            )}
          </>
        ) : (
          <>
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
                  <div className="mt-1 flex flex-col gap-1.5">
                    {strategy.entry_rules.map((group, gi) => (
                      <div key={gi} className="flex flex-wrap items-center gap-2">
                        {gi > 0 && <span className="text-[10px] font-bold uppercase text-muted">O</span>}
                        {group.map((c, ci) => (
                          <span key={ci} className="flex items-center gap-2">
                            {ci > 0 && <span className="text-[10px] font-bold uppercase text-muted">Y</span>}
                            <span className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-ink">
                              {conditionLabel(conditionCatalog, c)}
                            </span>
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-ink">{strategy.entry_conditions || "—"}</p>
                )}
              </div>
              <div>
                <span className="text-xs font-medium text-muted">Condiciones de salida</span>
                {strategy.exit_rules.length > 0 ? (
                  <div className="mt-1 flex flex-col gap-1.5">
                    {strategy.exit_rules.map((group, gi) => (
                      <div key={gi} className="flex flex-wrap items-center gap-2">
                        {gi > 0 && <span className="text-[10px] font-bold uppercase text-muted">O</span>}
                        {group.map((c, ci) => (
                          <span key={ci} className="flex items-center gap-2">
                            {ci > 0 && <span className="text-[10px] font-bold uppercase text-muted">Y</span>}
                            <span className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-ink">
                              {conditionLabel(conditionCatalog, c)}
                            </span>
                          </span>
                        ))}
                      </div>
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
          </>
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
                  <th className="pb-2 font-medium" colSpan={2} />
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
                    <td className="py-3 pr-4">
                      <button
                        onClick={() => setSelectedRunId(run.id)}
                        className={`text-sm font-semibold underline ${selectedRunId === run.id ? "text-ink" : "text-muted"}`}
                      >
                        {selectedRunId === run.id ? "Viendo" : "Ver detalle"}
                      </button>
                    </td>
                    <td className="py-3">
                      <button
                        onClick={() => deleteRun(run.id)}
                        disabled={deletingRunId === run.id}
                        className="text-sm font-semibold text-red-600 underline disabled:opacity-50"
                      >
                        {deletingRunId === run.id ? "Eliminando…" : "Eliminar"}
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
