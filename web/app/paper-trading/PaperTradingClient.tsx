"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import type { SavedStrategySummary } from "@/app/constructor/ConstructorClient";

// Único timeframe que soporta el tick de paper trading hoy (ver LOOKBACK_BARS en
// paper_trading/tick.py, que asume velas de 1h). Una estrategia puede declarar otras
// temporalidades para backtest, pero solo se puede paper-tradear en esta.
const PAPER_TRADING_TIMEFRAME = "1h";

export interface SessionSummary {
  id: number;
  strategy_id: number | null;
  strategy_name: string | null;
  strategy: string;
  symbol: string;
  timeframe: string;
  status: string;
  initial_equity: number;
  current_equity: number;
  last_tick_at: string | null;
  created_at: string;
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

function Field({
  label,
  value,
  onChange,
  step = "100",
  min = "100",
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

export function PaperTradingClient({
  initialSessions,
  initialError,
  strategies,
  strategiesError,
}: {
  initialSessions: SessionSummary[];
  initialError: string | null;
  strategies: SavedStrategySummary[];
  strategiesError: string | null;
}) {
  const [sessions, setSessions] = useState<SessionSummary[]>(initialSessions);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const paperTradeable = useMemo(() => strategies.filter((s) => s.timeframes.includes(PAPER_TRADING_TIMEFRAME)), [strategies]);

  const [strategyId, setStrategyId] = useState<number | null>(paperTradeable[0]?.id ?? null);
  const selectedStrategy = strategies.find((s) => s.id === strategyId) ?? null;
  const [symbol, setSymbol] = useState<string>(paperTradeable[0]?.symbols[0] ?? "");
  const [initialEquity, setInitialEquity] = useState(10000);

  const [showForm, setShowForm] = useState(initialSessions.length === 0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function selectStrategy(id: number) {
    setStrategyId(id);
    const strategy = strategies.find((s) => s.id === id);
    setSymbol(strategy?.symbols[0] ?? "");
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
    if (strategyId === null || !symbol) return;
    setCreating(true);
    setCreateError(null);

    try {
      const response = await fetch("/api/paper-trading/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_id: strategyId,
          symbol,
          timeframe: PAPER_TRADING_TIMEFRAME,
          initial_equity: initialEquity,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setCreateError(typeof data.detail === "string" ? data.detail : "No se pudo iniciar la sesión.");
        return;
      }

      setLoadError(null);
      setShowForm(false);
      await reloadSessions();
    } catch {
      setCreateError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setCreating(false);
    }
  }

  const activeCount = sessions.filter((s) => s.status === "active").length;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Paper Trading
            <InfoGuide>
              Paper Trading toma una de tus estrategias guardadas en el Constructor y simula su ejecución
              contra el mercado real en curso, sin usar plata real. Cada sesión corre el motor de backtest
              cada 15 minutos (vía un servicio cron) sobre las últimas velas cerradas del símbolo elegido, y
              actualiza el equity, la posición abierta y las operaciones cerradas.
              <br />
              <br />
              Solo se puede paper-tradear en 1h por ahora, y solo mercados que la estrategia declaró en el
              Constructor. Si no ves una estrategia acá, o su símbolo, revisá su configuración ahí primero.
              <br />
              <br />
              Podés tener varias sesiones corriendo en simultáneo. Esta pantalla lista todas tus sesiones
              (activas e históricas); hacé clic en &quot;Ver detalle&quot; para ver el equity, la posición
              abierta, los parámetros configurados y las operaciones cerradas de cada una, y desde ahí podés
              detenerla cuando quieras (queda guardada en el historial, no se borra).
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">Simulación en vivo sobre el mercado real, sin plata real</p>
        </div>
        <div className="flex items-center gap-3">
          <DataBadge
            live={activeCount > 0}
            label={activeCount > 0 ? `${activeCount} sesión(es) activa(s)` : "Sin sesiones activas"}
          />
          {paperTradeable.length > 0 && (
            <button
              onClick={() => setShowForm((v) => !v)}
              className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
            >
              {showForm ? "Cancelar" : "+ Nueva sesión"}
            </button>
          )}
        </div>
      </div>

      {loadError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus sesiones: </span>
          {loadError}
        </div>
      )}

      {strategiesError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus estrategias: </span>
          {strategiesError}
        </div>
      )}

      {!strategiesError && strategies.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Todavía no guardaste ninguna estrategia.{" "}
          <Link href="/constructor" className="font-semibold text-ink underline">
            Creá una en el Constructor
          </Link>{" "}
          para poder paper-tradearla.
        </div>
      )}

      {!strategiesError && strategies.length > 0 && paperTradeable.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Ninguna de tus estrategias declara la temporalidad 1h (la única que soporta paper trading por
          ahora).{" "}
          <Link href="/constructor" className="font-semibold text-ink underline">
            Agregala en el Constructor
          </Link>
          .
        </div>
      )}

      {showForm && paperTradeable.length > 0 && (
        <div className="rounded-3xl bg-panel p-8">
          <h2 className="text-lg font-bold text-ink">Iniciar sesión de paper trading</h2>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Estrategia</span>
              <select
                value={strategyId ?? ""}
                onChange={(e) => selectStrategy(Number(e.target.value))}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              >
                {paperTradeable.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Símbolo</span>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
              >
                {(selectedStrategy?.symbols ?? []).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted">Temporalidad</span>
              <input
                type="text"
                value={PAPER_TRADING_TIMEFRAME}
                disabled
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-muted"
              />
            </label>
            <Field label="Equity inicial ($)" value={initialEquity} onChange={setInitialEquity} />
          </div>

          <button
            onClick={createSession}
            disabled={creating || strategyId === null || !symbol}
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
                  <th className="pb-2 pr-4 font-medium">Estrategia</th>
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
                        {s.strategy_id ? (
                          <Link href={`/constructor/${s.strategy_id}`} className="underline">
                            {s.strategy_name ?? s.strategy}
                          </Link>
                        ) : (
                          (s.strategy_name ?? s.strategy)
                        )}
                      </td>
                      <td className="py-3 pr-4 text-ink">{s.symbol}</td>
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
