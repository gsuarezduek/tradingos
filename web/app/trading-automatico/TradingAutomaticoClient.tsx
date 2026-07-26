"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { EXCHANGES } from "@/lib/exchanges";
import type { SavedStrategySummary } from "@/app/constructor/ConstructorClient";
import type { Connection } from "@/app/operar/OperarClient";

// Misma limitación que paper trading: el tick asume velas de 1h.
const LIVE_TRADING_TIMEFRAME = "1h";

interface CurrentPosition {
  side: string;
  entry_price: number;
  quantity: number;
  stop_loss: number | null;
  take_profit: number | null;
  entry_timestamp: string;
  opened_at: string;
}

export interface LiveSessionSummary {
  id: number;
  strategy_id: number;
  strategy_name: string;
  strategy: string;
  broker_connection_id: number;
  broker_connection_label: string;
  exchange: string;
  symbol: string;
  timeframe: string;
  status: string;
  current_position: CurrentPosition | null;
  last_tick_at: string | null;
  created_at: string;
}

function exchangeLabel(value: string): string {
  return EXCHANGES.find((e) => e.value === value)?.label ?? value;
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

function PositionCell({ position }: { position: CurrentPosition | null }) {
  if (!position) return <span className="text-muted">Flat</span>;
  return (
    <span className="text-ink">
      <span className="font-semibold uppercase">{position.side}</span> · qty{" "}
      {position.quantity.toLocaleString("es-AR", { maximumFractionDigits: 6 })} @{" "}
      {position.entry_price.toLocaleString("es-AR", { maximumFractionDigits: 2 })}
    </span>
  );
}

export function TradingAutomaticoClient({
  initialSessions,
  sessionsError,
  strategies,
  strategiesError,
  connections,
  connectionsError,
}: {
  initialSessions: LiveSessionSummary[];
  sessionsError: string | null;
  strategies: SavedStrategySummary[];
  strategiesError: string | null;
  connections: Connection[];
  connectionsError: string | null;
}) {
  const [sessions, setSessions] = useState<LiveSessionSummary[]>(initialSessions);
  const [loadError, setLoadError] = useState<string | null>(sessionsError);

  const liveTradeable = useMemo(() => strategies.filter((s) => s.timeframes.includes(LIVE_TRADING_TIMEFRAME)), [strategies]);
  const tradableConnections = useMemo(() => connections.filter((c) => c.trading_enabled), [connections]);

  const canCreate = liveTradeable.length > 0 && tradableConnections.length > 0;

  const [strategyId, setStrategyId] = useState<number | null>(liveTradeable[0]?.id ?? null);
  const selectedStrategy = strategies.find((s) => s.id === strategyId) ?? null;
  const [connectionId, setConnectionId] = useState<number | null>(tradableConnections[0]?.id ?? null);
  const [symbol, setSymbol] = useState<string>(liveTradeable[0]?.symbols[0] ?? "");

  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState<"form" | "review">("form");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function selectStrategy(id: number) {
    setStrategyId(id);
    const strategy = strategies.find((s) => s.id === id);
    setSymbol(strategy?.symbols[0] ?? "");
  }

  async function reloadSessions() {
    try {
      const response = await fetch("/api/live-trading/sessions");
      const data = await response.json();
      if (response.ok) setSessions(data);
    } catch {
      // silencioso: si falla el refresh, se mantiene el estado anterior
    }
  }

  async function createSession() {
    if (strategyId === null || connectionId === null || !symbol) return;
    setCreating(true);
    setCreateError(null);

    try {
      const response = await fetch("/api/live-trading/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_id: strategyId,
          broker_connection_id: connectionId,
          symbol,
          timeframe: LIVE_TRADING_TIMEFRAME,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setCreateError(typeof data.detail === "string" ? data.detail : "No se pudo activar la estrategia.");
        return;
      }

      setLoadError(null);
      setShowForm(false);
      setStep("form");
      await reloadSessions();
    } catch {
      setCreateError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setCreating(false);
    }
  }

  const selectedConnection = connections.find((c) => c.id === connectionId) ?? null;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Trading Automático
            <InfoGuide>
              Activa una de tus estrategias del Constructor para que opere sola, con plata real, contra una
              cuenta con trading habilitado. Cada 15 minutos (mismo cron que Paper Trading) el sistema
              recalcula qué debería estar pasando ahora mismo y, si corresponde, manda una orden real market
              (misma ruta que Operar Manual).
              <br />
              <br />
              A diferencia de paper trading, una orden real ya ejecutada no se puede &quot;recalcular&quot; — el
              sistema solo actúa sobre la diferencia entre lo que de verdad tenés abierto y lo que la
              estrategia dice que debería estar abierto ahora. Recomendamos paper-tradear una estrategia un
              tiempo antes de pasarla a real.
              <br />
              <br />
              &quot;Detener&quot; para el tick, pero <strong>no cierra sola una posición real abierta</strong>{" "}
              — esa decisión es tuya, se cierra manualmente desde Operar Manual si hace falta.
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">Estrategias del Constructor operando solas con plata real</p>
        </div>
        <div className="flex items-center gap-3">
          <DataBadge
            live={sessions.some((s) => s.status === "active")}
            label={sessions.some((s) => s.status === "active") ? "Sesiones activas" : "Sin sesiones activas"}
          />
          {canCreate && (
            <button
              onClick={() => {
                setShowForm((v) => !v);
                setStep("form");
              }}
              className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
            >
              {showForm ? "Cancelar" : "+ Activar estrategia"}
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
      {connectionsError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus conexiones: </span>
          {connectionsError}
        </div>
      )}

      {!strategiesError && strategies.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Todavía no guardaste ninguna estrategia.{" "}
          <Link href="/constructor" className="font-semibold text-ink underline">
            Creá una en el Constructor
          </Link>
          .
        </div>
      )}
      {!strategiesError && strategies.length > 0 && liveTradeable.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Ninguna de tus estrategias declara la temporalidad 1h (la única soportada por ahora).{" "}
          <Link href="/constructor" className="font-semibold text-ink underline">
            Agregala en el Constructor
          </Link>
          .
        </div>
      )}
      {!connectionsError && connections.length > 0 && tradableConnections.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Ninguna de tus cuentas conectadas tiene trading habilitado.{" "}
          <Link href="/conexiones" className="font-semibold text-ink underline">
            Habilitalo en Conexión con Exchanges
          </Link>
          .
        </div>
      )}
      {!connectionsError && connections.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Todavía no conectaste ninguna cuenta.{" "}
          <Link href="/conexiones" className="font-semibold text-ink underline">
            Conectá una en Conexión con Exchanges
          </Link>
          .
        </div>
      )}

      {showForm && canCreate && (
        <div className="rounded-3xl bg-panel p-8">
          <h2 className="text-lg font-bold text-ink">Activar estrategia en real</h2>

          {step === "form" && (
            <>
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted">Estrategia</span>
                  <select
                    value={strategyId ?? ""}
                    onChange={(e) => selectStrategy(Number(e.target.value))}
                    className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
                  >
                    {liveTradeable.map((s) => (
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
                  <span className="text-xs font-medium text-muted">Cuenta (con trading habilitado)</span>
                  <select
                    value={connectionId ?? ""}
                    onChange={(e) => setConnectionId(Number(e.target.value))}
                    className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
                  >
                    {tradableConnections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label} ({exchangeLabel(c.exchange)})
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                onClick={() => setStep("review")}
                disabled={strategyId === null || connectionId === null || !symbol}
                className="mt-6 rounded-xl border border-border px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50"
              >
                Revisar
              </button>
            </>
          )}

          {step === "review" && selectedStrategy && selectedConnection && (
            <div className="mt-6 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-ink">
              <p>
                Vas a activar <span className="font-semibold">{selectedStrategy.name}</span> para operar sola en{" "}
                <span className="font-semibold">{symbol}</span> ({LIVE_TRADING_TIMEFRAME}) contra{" "}
                <span className="font-semibold">
                  {selectedConnection.label} ({exchangeLabel(selectedConnection.exchange)})
                </span>
                . A partir de ahora, cada 15 minutos el sistema puede mandar órdenes reales de compra/venta por
                su cuenta con la plata de esa cuenta, sin pedirte confirmación por cada una. Esta primera
                versión no tiene ningún límite de riesgo propio más allá de la config de la estrategia.
              </p>
              <div className="mt-4 flex gap-3">
                <button
                  onClick={() => setStep("form")}
                  disabled={creating}
                  className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted"
                >
                  Volver
                </button>
                <button
                  onClick={createSession}
                  disabled={creating}
                  className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {creating ? "Activando…" : "Confirmar y activar"}
                </button>
              </div>
            </div>
          )}

          {createError && (
            <p className="mt-4 text-sm text-muted">
              <span className="font-semibold text-ink">No se pudo activar: </span>
              {createError}
            </p>
          )}
        </div>
      )}

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Sesiones de trading en vivo</h2>

        {sessions.length === 0 && <p className="mt-4 text-sm text-muted">Todavía no activaste ninguna estrategia en real.</p>}

        {sessions.length > 0 && (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Estrategia</th>
                  <th className="pb-2 pr-4 font-medium">Cuenta</th>
                  <th className="pb-2 pr-4 font-medium">Símbolo</th>
                  <th className="pb-2 pr-4 font-medium">Estado</th>
                  <th className="pb-2 pr-4 font-medium">Posición actual</th>
                  <th className="pb-2 pr-4 font-medium">Última actualización</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0">
                    <td className="py-3 pr-4 font-semibold text-ink">
                      <Link href={`/constructor/${s.strategy_id}`} className="underline">
                        {s.strategy_name}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-ink">
                      {s.broker_connection_label} <span className="text-muted">({exchangeLabel(s.exchange)})</span>
                    </td>
                    <td className="py-3 pr-4 text-ink">{s.symbol}</td>
                    <td className="py-3 pr-4">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="py-3 pr-4">
                      <PositionCell position={s.current_position} />
                    </td>
                    <td className="py-3 pr-4 text-muted">
                      {s.last_tick_at
                        ? new Date(s.last_tick_at).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
                        : "todavía no corrió"}
                    </td>
                    <td className="py-3">
                      <Link href={`/trading-automatico/${s.id}`} className="text-sm font-semibold text-ink underline">
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
