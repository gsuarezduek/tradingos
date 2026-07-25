"use client";

import { useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
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

export interface SessionDetail {
  id: number;
  strategy: string;
  symbol: string;
  timeframe: string;
  status: string;
  config: StrategyConfigJSON;
  initial_equity: number;
  current_equity: number;
  open_position: OpenPosition | null;
  last_tick_at: string | null;
  created_at: string;
  equity_curve: { timestamp: string; equity: number }[];
  trades: Trade[];
}

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

export function SessionDetailClient({
  sessionId,
  initialSession,
  initialError,
}: {
  sessionId: string;
  initialSession: SessionDetail | null;
  initialError: string | null;
}) {
  const [session, setSession] = useState<SessionDetail | null>(initialSession);
  const [loadError] = useState<string | null>(initialError);
  const [stopping, setStopping] = useState(false);

  async function stopSession() {
    if (!session) return;
    setStopping(true);
    try {
      await fetch(`/api/paper-trading/sessions/${session.id}/stop`, { method: "POST" });
      const response = await fetch(`/api/paper-trading/sessions/${sessionId}`);
      const data = await response.json();
      if (response.ok) setSession(data);
    } finally {
      setStopping(false);
    }
  }

  if (loadError || !session) {
    return (
      <div className="flex flex-col gap-8">
        <Link href="/paper-trading" className="text-sm font-semibold text-ink underline">
          ← Volver a Paper Trading
        </Link>
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo cargar la sesión: </span>
          {loadError ?? "sesión no encontrada"}
        </div>
      </div>
    );
  }

  const isActive = session.status === "active";
  const trades = session.trades;
  const winRatePct = trades.length > 0 ? (trades.filter((t) => t.pnl > 0).length / trades.length) * 100 : 0;
  const chartData = session.equity_curve.slice(-5).map((point) => ({
    label: new Date(point.timestamp).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit" }),
    value: point.equity,
  }));
  const config = session.config;
  const emaFast = config.indicators?.ema_fast?.period;
  const emaSlow = config.indicators?.ema_slow?.period;
  const atr = config.indicators?.atr?.period;
  const atrMinPct = config.indicators?.atr?.min_value_pct;

  return (
    <div className="flex flex-col gap-8">
      <Link href="/paper-trading" className="text-sm font-semibold text-ink underline">
        ← Volver a Paper Trading
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            {session.symbol} · {session.strategy}
            <InfoGuide>
              Este es el detalle de una sesión de paper trading: simula la estrategia configurada contra
              el mercado real, sin plata real. El gráfico muestra el equity de los últimos ticks (corre
              cada 15 minutos), el gauge muestra el win rate de las operaciones cerradas, y a la derecha
              ves el capital actual y la cantidad de operaciones. Abajo están los parámetros exactos con
              los que se lanzó esta sesión, la posición abierta en este momento (si hay una), y el
              historial de operaciones ya cerradas. El botón &quot;Detener&quot; para la sesión (deja de
              recibir ticks) pero no la borra: queda en el historial.
            </InfoGuide>
          </h1>
          <p className="text-xs text-muted">
            {isActive ? "Activa" : "Detenida"} · Iniciada: {new Date(session.created_at).toLocaleString("es-AR")} · Última
            actualización: {session.last_tick_at ? new Date(session.last_tick_at).toLocaleString("es-AR") : "todavía no corrió ningún tick"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <DataBadge live={isActive} label={isActive ? "Sesión activa" : "Sesión detenida"} />
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
      </div>

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
        <h2 className="text-lg font-bold text-ink">Parámetros configurados</h2>
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <ConfigField label="Símbolo" value={config.symbol} />
          <ConfigField label="Timeframe" value={config.timeframe} />
          <ConfigField label="Equity inicial" value={`$${session.initial_equity.toLocaleString("es-AR")}`} />
          <ConfigField label="EMA rápida" value={emaFast != null ? String(emaFast) : "—"} />
          <ConfigField label="EMA lenta" value={emaSlow != null ? String(emaSlow) : "—"} />
          <ConfigField label="ATR (períodos)" value={atr != null ? String(atr) : "—"} />
          <ConfigField label="ATR mínimo" value={pct(atrMinPct)} />
          <ConfigField label="Stop Loss" value={pct(config.stop_loss_pct)} />
          <ConfigField label="Take Profit" value={pct(config.take_profit_pct)} />
          <ConfigField label="Trailing Stop" value={pct(config.trailing_stop_pct)} />
          <ConfigField label="Riesgo por operación" value={pct(config.risk_per_trade)} />
        </div>
      </div>

      <div className="rounded-3xl bg-panel p-8">
        {session.open_position && (
          <div className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-ink">
            <span className="font-semibold uppercase">{session.open_position.side}</span> abierta @{" "}
            {session.open_position.entry_price.toLocaleString("es-AR", { maximumFractionDigits: 2 })} · qty{" "}
            {session.open_position.quantity.toLocaleString("es-AR", { maximumFractionDigits: 6 })}
          </div>
        )}
        {!session.open_position && <p className="text-sm text-muted">Sin posición abierta en este momento.</p>}

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
    </div>
  );
}
