"use client";

import { useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { EXCHANGES } from "@/lib/exchanges";

interface CurrentPosition {
  side: string;
  entry_price: number;
  quantity: number;
  stop_loss: number | null;
  take_profit: number | null;
  entry_timestamp: string;
  opened_at: string;
}

interface Trade {
  side: string;
  entry_timestamp: string;
  exit_timestamp: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
}

interface Order {
  id: number;
  side: string;
  amount_usdt: number;
  filled_quantity: number | null;
  avg_price: number | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface SessionDetail {
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
  trades: Trade[];
  orders: Order[];
}

function exchangeLabel(value: string): string {
  return EXCHANGES.find((e) => e.value === value)?.label ?? value;
}

function fmt(value: number, digits = 2): string {
  return value.toLocaleString("es-AR", { maximumFractionDigits: digits });
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
    if (!confirm("¿Detener esta sesión? Recordá que esto NO cierra sola una posición real abierta.")) return;
    setStopping(true);
    try {
      await fetch(`/api/live-trading/sessions/${session.id}/stop`, { method: "POST" });
      const response = await fetch(`/api/live-trading/sessions/${sessionId}`);
      const data = await response.json();
      if (response.ok) setSession(data);
    } finally {
      setStopping(false);
    }
  }

  if (loadError || !session) {
    return (
      <div className="flex flex-col gap-8">
        <Link href="/trading-automatico" className="text-sm font-semibold text-ink underline">
          ← Volver a Trading Automático
        </Link>
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo cargar la sesión: </span>
          {loadError ?? "sesión no encontrada"}
        </div>
      </div>
    );
  }

  const isActive = session.status === "active";
  const position = session.current_position;

  return (
    <div className="flex flex-col gap-8">
      <Link href="/trading-automatico" className="text-sm font-semibold text-ink underline">
        ← Volver a Trading Automático
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            {session.symbol} ·{" "}
            <Link href={`/constructor/${session.strategy_id}`} className="underline">
              {session.strategy_name}
            </Link>
            <InfoGuide>
              Esta sesión opera con plata real en{" "}
              <span className="font-semibold">
                {session.broker_connection_label} ({exchangeLabel(session.exchange)})
              </span>
              . Cada tick (cada 15 minutos) puede mandar una orden real de compra o venta si la estrategia lo
              indica. &quot;Detener&quot; para el tick, pero no cierra sola una posición real que ya esté
              abierta — esa decisión es tuya, hacela desde Operar Manual.
            </InfoGuide>
          </h1>
          <p className="text-xs text-muted">
            {isActive ? "Activa" : "Detenida"} · Activada: {new Date(session.created_at).toLocaleString("es-AR")} · Última
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

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Posición actual</h2>
        {!position && <p className="mt-3 text-sm text-muted">Flat — sin posición real abierta en este momento.</p>}
        {position && (
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <span className="text-xs font-medium text-muted">Lado</span>
              <div className="text-sm font-semibold uppercase text-ink">{position.side}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-muted">Cantidad</span>
              <div className="text-sm text-ink">{fmt(position.quantity, 6)}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-muted">Precio de entrada</span>
              <div className="text-sm text-ink">{fmt(position.entry_price)}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-muted">Abierta desde</span>
              <div className="text-sm text-ink">{new Date(position.opened_at).toLocaleString("es-AR")}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-muted">Stop Loss</span>
              <div className="text-sm text-ink">{position.stop_loss != null ? fmt(position.stop_loss) : "—"}</div>
            </div>
            <div>
              <span className="text-xs font-medium text-muted">Take Profit</span>
              <div className="text-sm text-ink">{position.take_profit != null ? fmt(position.take_profit) : "—"}</div>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Operaciones cerradas</h2>
        {session.trades.length === 0 && <p className="mt-4 text-sm text-muted">Todavía no se cerró ninguna operación.</p>}
        {session.trades.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Lado</th>
                  <th className="pb-2 pr-4 font-medium">Entrada</th>
                  <th className="pb-2 pr-4 font-medium">Salida</th>
                  <th className="pb-2 pr-4 font-medium">Cantidad</th>
                  <th className="pb-2 font-medium">PnL</th>
                </tr>
              </thead>
              <tbody>
                {session.trades
                  .slice()
                  .reverse()
                  .map((trade, i) => (
                    <tr key={i} className="border-b border-border last:border-0">
                      <td className="py-2 pr-4 font-semibold uppercase text-ink">{trade.side}</td>
                      <td className="py-2 pr-4 text-ink">{new Date(trade.entry_timestamp).toLocaleString("es-AR")}</td>
                      <td className="py-2 pr-4 text-ink">{new Date(trade.exit_timestamp).toLocaleString("es-AR")}</td>
                      <td className="py-2 pr-4 text-ink">{fmt(trade.quantity, 6)}</td>
                      <td className={`py-2 ${trade.pnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>{fmt(trade.pnl)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Órdenes enviadas</h2>
        {session.orders.length === 0 && <p className="mt-4 text-sm text-muted">Todavía no se mandó ninguna orden.</p>}
        {session.orders.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Fecha</th>
                  <th className="pb-2 pr-4 font-medium">Lado</th>
                  <th className="pb-2 pr-4 font-medium">Monto (USDT)</th>
                  <th className="pb-2 pr-4 font-medium">Cantidad ejecutada</th>
                  <th className="pb-2 pr-4 font-medium">Precio</th>
                  <th className="pb-2 pr-4 font-medium">Estado</th>
                  <th className="pb-2 font-medium">Detalle</th>
                </tr>
              </thead>
              <tbody>
                {session.orders.map((o) => (
                  <tr key={o.id} className="border-b border-border last:border-0">
                    <td className="py-2 pr-4 text-ink">{new Date(o.created_at).toLocaleString("es-AR")}</td>
                    <td className="py-2 pr-4 text-ink">{o.side === "buy" ? "Compra" : "Venta"}</td>
                    <td className="py-2 pr-4 text-ink">{fmt(o.amount_usdt)}</td>
                    <td className="py-2 pr-4 text-ink">{o.filled_quantity != null ? fmt(o.filled_quantity, 6) : "—"}</td>
                    <td className="py-2 pr-4 text-ink">{o.avg_price != null ? fmt(o.avg_price) : "—"}</td>
                    <td className={`py-2 pr-4 ${o.status === "submitted" ? "text-emerald-600" : "text-red-600"}`}>
                      {o.status === "submitted" ? "Enviada" : "Rechazada"}
                    </td>
                    <td className="py-2 text-ink">{o.error_message ?? "—"}</td>
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
