"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { EXCHANGES } from "@/lib/exchanges";

export interface Connection {
  id: number;
  exchange: string;
  label: string;
  created_at: string;
  trading_enabled: boolean;
}

interface Order {
  id: number;
  exchange: string;
  symbol: string;
  side: string;
  amount_usdt: number;
  filled_quantity: number | null;
  avg_price: number | null;
  status: string;
  exchange_order_id: string | null;
  error_message: string | null;
  created_at: string;
}

const FALLBACK_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"];

function exchangeLabel(value: string): string {
  return EXCHANGES.find((e) => e.value === value)?.label ?? value;
}

function formatUsdt(value: number): string {
  return value.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
    </label>
  );
}

function TradingPanel({
  connection,
  symbols,
  orders,
  ordersLoading,
  ordersError,
  onOrderPlaced,
}: {
  connection: Connection;
  symbols: string[];
  orders: Order[] | undefined;
  ordersLoading: boolean;
  ordersError: string | undefined;
  onOrderPlaced: () => void;
}) {
  const usdtSymbols = symbols.filter((s) => s.endsWith("USDT"));
  const symbolOptions = usdtSymbols.length > 0 ? usdtSymbols : FALLBACK_SYMBOLS;

  const [symbol, setSymbol] = useState(symbolOptions[0]);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [amountUsdt, setAmountUsdt] = useState("");
  const [step, setStep] = useState<"form" | "review">("form");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const amountUsdtNumber = Number(amountUsdt);
  const canReview = symbol && amountUsdtNumber > 0;

  async function submitOrder() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await fetch(`/api/brokers/${connection.exchange}/connections/${connection.id}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, side, amount_usdt: amountUsdtNumber }),
      });
      const data = await response.json();
      if (!response.ok) {
        setSubmitError(typeof data.detail === "string" ? data.detail : "No se pudo enviar la orden.");
        return;
      }
      setStep("form");
      setAmountUsdt("");
      onOrderPlaced();
    } catch {
      setSubmitError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-4">
      {step === "form" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted">Símbolo</span>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
            >
              {symbolOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted">Lado</span>
            <select
              value={side}
              onChange={(e) => setSide(e.target.value as "buy" | "sell")}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
            >
              <option value="buy">Comprar</option>
              <option value="sell">Vender</option>
            </select>
          </label>
          <TextField
            label="Monto (USDT)"
            value={amountUsdt}
            onChange={setAmountUsdt}
            type="number"
            placeholder="Ej: 10"
          />
        </div>
      )}

      {step === "form" && (
        <button
          onClick={() => setStep("review")}
          disabled={!canReview}
          className="mt-4 rounded-xl border border-border px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50"
        >
          Revisar orden
        </button>
      )}

      {step === "review" && (
        <div className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-ink">
          <p>
            Vas a <span className="font-semibold">{side === "buy" ? "comprar" : "vender"}</span>{" "}
            <span className="font-semibold">{symbol}</span> por{" "}
            <span className="font-semibold">{amountUsdt} USDT</span> a precio de mercado en{" "}
            <span className="font-semibold">{exchangeLabel(connection.exchange)}</span>. Esta acción usa dinero real y
            no se puede deshacer.
          </p>
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => setStep("form")}
              disabled={submitting}
              className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted"
            >
              Volver
            </button>
            <button
              onClick={submitOrder}
              disabled={submitting}
              className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {submitting ? "Enviando…" : "Confirmar y enviar"}
            </button>
          </div>
        </div>
      )}

      {submitError && (
        <p className="mt-3 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo enviar: </span>
          {submitError}
        </p>
      )}

      <h4 className="mt-6 text-xs font-bold uppercase tracking-wide text-muted">Historial de órdenes</h4>
      {ordersLoading && <p className="mt-2 text-sm text-muted">Cargando historial…</p>}
      {ordersError && <p className="mt-2 text-sm text-muted">{ordersError}</p>}
      {orders && orders.length === 0 && <p className="mt-2 text-sm text-muted">Todavía no enviaste ninguna orden.</p>}
      {orders && orders.length > 0 && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                <th className="pb-2 pr-4 font-medium">Fecha</th>
                <th className="pb-2 pr-4 font-medium">Símbolo</th>
                <th className="pb-2 pr-4 font-medium">Lado</th>
                <th className="pb-2 pr-4 font-medium">Monto (USDT)</th>
                <th className="pb-2 pr-4 font-medium">Cantidad ejecutada</th>
                <th className="pb-2 pr-4 font-medium">Precio</th>
                <th className="pb-2 pr-4 font-medium">Estado</th>
                <th className="pb-2 font-medium">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-b border-border last:border-0">
                  <td className="py-2 pr-4 text-ink">{new Date(o.created_at).toLocaleString("es-AR")}</td>
                  <td className="py-2 pr-4 font-semibold text-ink">{o.symbol}</td>
                  <td className="py-2 pr-4 text-ink">{o.side === "buy" ? "Compra" : "Venta"}</td>
                  <td className="py-2 pr-4 text-ink">{formatUsdt(o.amount_usdt)}</td>
                  <td className="py-2 pr-4 text-ink">
                    {o.filled_quantity != null ? o.filled_quantity.toLocaleString("es-AR", { maximumFractionDigits: 8 }) : "—"}
                  </td>
                  <td className="py-2 pr-4 text-ink">{o.avg_price ? formatUsdt(o.avg_price) : "—"}</td>
                  <td className={`py-2 pr-4 ${o.status === "submitted" ? "text-emerald-600" : "text-red-600"}`}>
                    {o.status === "submitted" ? "Enviada" : "Rechazada"}
                  </td>
                  <td className="py-2 text-ink">{o.error_message ?? o.exchange_order_id ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function OperarClient({
  initialConnections,
  initialError,
  symbols,
}: {
  initialConnections: Connection[];
  initialError: string | null;
  symbols: string[];
}) {
  const [connections] = useState<Connection[]>(initialConnections);
  const [loadError] = useState<string | null>(initialError);
  const [ordersById, setOrdersById] = useState<Record<number, Order[]>>({});
  const [ordersLoadingId, setOrdersLoadingId] = useState<number | null>(null);
  const [ordersErrorById, setOrdersErrorById] = useState<Record<number, string>>({});

  async function fetchOrders(connection: Connection) {
    setOrdersLoadingId(connection.id);
    try {
      const response = await fetch(`/api/brokers/${connection.exchange}/connections/${connection.id}/orders`);
      const data = await response.json();
      if (!response.ok) {
        setOrdersErrorById((prev) => ({
          ...prev,
          [connection.id]: typeof data.detail === "string" ? data.detail : "No se pudo cargar el historial.",
        }));
        return;
      }
      setOrdersById((prev) => ({ ...prev, [connection.id]: data }));
    } catch {
      setOrdersErrorById((prev) => ({ ...prev, [connection.id]: "No se pudo conectar con la API." }));
    } finally {
      setOrdersLoadingId(null);
    }
  }

  // El historial de cada cuenta operable se pide apenas se conoce la lista, no
  // detrás de un toggle: en esta página el usuario vino específicamente a operar.
  useEffect(() => {
    for (const connection of connections) {
      if (connection.trading_enabled && !(connection.id in ordersById)) {
        fetchOrders(connection);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connections]);

  const tradableConnections = connections.filter((c) => c.trading_enabled);
  const disabledConnections = connections.filter((c) => !c.trading_enabled);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Operar Manual</h1>
          <p className="text-sm text-muted">Enviá órdenes market spot reales en tus cuentas con trading habilitado</p>
        </div>
        <DataBadge
          live={tradableConnections.length > 0}
          label={tradableConnections.length > 0 ? "Cuentas operables" : "Sin trading habilitado"}
        />
      </div>

      {loadError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus conexiones: </span>
          {loadError}
        </div>
      )}

      {!loadError && connections.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Todavía no conectaste ninguna cuenta.{" "}
          <Link href="/conexiones" className="font-semibold text-ink underline">
            Conectá una en Conexión con Exchanges
          </Link>
          .
        </div>
      )}

      {!loadError && connections.length > 0 && tradableConnections.length === 0 && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Ninguna de tus cuentas tiene trading habilitado.{" "}
          <Link href="/conexiones" className="font-semibold text-ink underline">
            Habilitalo en Conexión con Exchanges
          </Link>
          .
        </div>
      )}

      {tradableConnections.length > 0 && (
        <div className="flex flex-col gap-4">
          {tradableConnections.map((connection) => (
            <div key={`${connection.exchange}-${connection.id}`} className="rounded-3xl bg-panel p-8">
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-ink">{connection.label}</h3>
                <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium text-muted">
                  {exchangeLabel(connection.exchange)}
                </span>
              </div>
              <TradingPanel
                connection={connection}
                symbols={symbols}
                orders={ordersById[connection.id]}
                ordersLoading={ordersLoadingId === connection.id}
                ordersError={ordersErrorById[connection.id]}
                onOrderPlaced={() => fetchOrders(connection)}
              />
            </div>
          ))}
        </div>
      )}

      {disabledConnections.length > 0 && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <p className="font-semibold text-ink">Cuentas conectadas sin trading habilitado</p>
          <ul className="mt-2 list-disc pl-5">
            {disabledConnections.map((c) => (
              <li key={`${c.exchange}-${c.id}`}>
                {c.label} ({exchangeLabel(c.exchange)})
              </li>
            ))}
          </ul>
          <p className="mt-3">
            Habilitá trading en{" "}
            <Link href="/conexiones" className="font-semibold text-ink underline">
              Conexión con Exchanges
            </Link>{" "}
            para poder operar con ellas acá.
          </p>
        </div>
      )}
    </div>
  );
}
