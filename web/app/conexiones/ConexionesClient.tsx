"use client";

import { useEffect, useState } from "react";
import { DataBadge } from "@/components/DataBadge";
import { EXCHANGES } from "@/lib/exchanges";

interface SpotBalance {
  asset: string;
  free: number;
  locked: number;
  total: number;
  usdt_value: number | null;
}

interface FuturesBalance {
  asset: string;
  balance: number;
  available_balance: number;
  cross_unrealized_pnl: number;
}

interface SectionResult<T> {
  ok: boolean;
  balances?: T[];
  error?: string;
  // Solo la sección spot lo trae — null si no se pudo obtener el precio de ningún
  // activo (falla del endpoint público de precios), no si faltan algunos.
  usdt_total?: number | null;
}

interface ExchangeBalancesResponse {
  spot: SectionResult<SpotBalance>;
  // Solo Binance soporta Futuros por ahora (ver InfoGuide/plan): ausente para el
  // resto, no un objeto vacío, así el panel sabe si tiene que mostrar la columna.
  futures_usdm?: SectionResult<FuturesBalance>;
}

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

function BalancesPanel({ result }: { result: ExchangeBalancesResponse }) {
  return (
    <div className={`grid grid-cols-1 gap-6 ${result.futures_usdm ? "lg:grid-cols-2" : ""}`}>
      <div>
        <h3 className="text-sm font-bold text-ink">Spot</h3>
        {!result.spot.ok && (
          <p className="mt-3 text-sm text-muted">
            <span className="font-semibold text-ink">No disponible: </span>
            {result.spot.error}
          </p>
        )}
        {result.spot.ok && result.spot.balances && result.spot.balances.length === 0 && (
          <p className="mt-3 text-sm text-muted">No hay saldos con balance mayor a cero.</p>
        )}
        {result.spot.ok && result.spot.balances && result.spot.balances.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-4 font-medium">Activo</th>
                  <th className="pb-2 pr-4 font-medium">Libre</th>
                  <th className="pb-2 pr-4 font-medium">Bloqueado</th>
                  <th className="pb-2 pr-4 font-medium">Total</th>
                  <th className="pb-2 font-medium">Equivalente en USDT</th>
                </tr>
              </thead>
              <tbody>
                {result.spot.balances.map((b) => (
                  <tr key={b.asset} className="border-b border-border last:border-0">
                    <td className="py-2 pr-4 font-semibold text-ink">{b.asset}</td>
                    <td className="py-2 pr-4 text-ink">{b.free.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                    <td className="py-2 pr-4 text-ink">{b.locked.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                    <td className="py-2 pr-4 text-ink">{b.total.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                    <td className="py-2 text-ink">{b.usdt_value !== null ? formatUsdt(b.usdt_value) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {result.futures_usdm && (
        <div>
          <h3 className="text-sm font-bold text-ink">Futuros (USD-M)</h3>
          {!result.futures_usdm.ok && (
            <p className="mt-3 text-sm text-muted">
              <span className="font-semibold text-ink">No disponible: </span>
              {result.futures_usdm.error}
            </p>
          )}
          {result.futures_usdm.ok && result.futures_usdm.balances && result.futures_usdm.balances.length === 0 && (
            <p className="mt-3 text-sm text-muted">No hay saldos con balance mayor a cero.</p>
          )}
          {result.futures_usdm.ok && result.futures_usdm.balances && result.futures_usdm.balances.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                    <th className="pb-2 pr-4 font-medium">Activo</th>
                    <th className="pb-2 pr-4 font-medium">Balance</th>
                    <th className="pb-2 pr-4 font-medium">Disponible</th>
                    <th className="pb-2 font-medium">PnL no realizado</th>
                  </tr>
                </thead>
                <tbody>
                  {result.futures_usdm.balances.map((b) => (
                    <tr key={b.asset} className="border-b border-border last:border-0">
                      <td className="py-2 pr-4 font-semibold text-ink">{b.asset}</td>
                      <td className="py-2 pr-4 text-ink">{b.balance.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                      <td className="py-2 pr-4 text-ink">
                        {b.available_balance.toLocaleString("es-AR", { maximumFractionDigits: 8 })}
                      </td>
                      <td className={`py-2 ${b.cross_unrealized_pnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {b.cross_unrealized_pnl.toLocaleString("es-AR", { maximumFractionDigits: 8 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EnableTradingModal({
  connection,
  onConfirm,
  onCancel,
  confirming,
}: {
  connection: Connection;
  onConfirm: () => void;
  onCancel: () => void;
  confirming: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-3xl bg-panel p-8">
        <h3 className="text-lg font-bold text-ink">Habilitar trading real</h3>
        <p className="mt-3 text-sm text-muted">
          Estás por habilitar el envío de <span className="font-semibold text-ink">órdenes reales con dinero real</span>{" "}
          en <span className="font-semibold text-ink">{connection.label}</span> ({exchangeLabel(connection.exchange)}).
          Cada orden todavía va a pedir una confirmación aparte antes de enviarse, pero a partir de ahora esta conexión
          va a poder operar. Podés desactivarlo en cualquier momento.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onCancel} className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted">
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            disabled={confirming}
            className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {confirming ? "Habilitando…" : "Sí, habilitar trading"}
          </button>
        </div>
      </div>
    </div>
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
    <div className="mt-6 border-t border-border pt-6">
      <h3 className="text-sm font-bold text-ink">Operar (orden market, spot)</h3>

      {step === "form" && (
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
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
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-ink">
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

export function ConexionesClient({
  initialConnections,
  initialError,
  symbols,
}: {
  initialConnections: Connection[];
  initialError: string | null;
  symbols: string[];
}) {
  const [connections, setConnections] = useState<Connection[]>(initialConnections);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const [exchange, setExchange] = useState(EXCHANGES[0].value);
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [balancesById, setBalancesById] = useState<Record<number, ExchangeBalancesResponse>>({});
  const [loadingIds, setLoadingIds] = useState<Set<number>>(new Set());
  const [balancesErrorById, setBalancesErrorById] = useState<Record<number, string>>({});

  const [tradingConnectionId, setTradingConnectionId] = useState<number | null>(null);
  const [confirmingConnection, setConfirmingConnection] = useState<Connection | null>(null);
  const [togglingTradingId, setTogglingTradingId] = useState<number | null>(null);
  const [ordersById, setOrdersById] = useState<Record<number, Order[]>>({});
  const [ordersLoadingId, setOrdersLoadingId] = useState<number | null>(null);
  const [ordersErrorById, setOrdersErrorById] = useState<Record<number, string>>({});

  const requiresPassphrase = EXCHANGES.find((e) => e.value === exchange)?.requiresPassphrase ?? false;

  async function fetchBalances(connection: Connection) {
    setLoadingIds((prev) => new Set(prev).add(connection.id));
    try {
      const response = await fetch(`/api/brokers/${connection.exchange}/connections/${connection.id}/balances`);
      const data = await response.json();
      if (!response.ok) {
        setBalancesErrorById((prev) => ({
          ...prev,
          [connection.id]: typeof data.detail === "string" ? data.detail : "No se pudieron cargar los saldos.",
        }));
        return;
      }
      setBalancesById((prev) => ({ ...prev, [connection.id]: data }));
    } catch {
      setBalancesErrorById((prev) => ({ ...prev, [connection.id]: "No se pudo conectar con la API." }));
    } finally {
      setLoadingIds((prev) => {
        const next = new Set(prev);
        next.delete(connection.id);
        return next;
      });
    }
  }

  // Se piden los saldos de todas las conexiones apenas se conoce la lista, no solo
  // al expandir "Ver saldos": el total en USDT junto al nombre tiene que estar
  // disponible sin que el usuario tenga que hacer nada. Implica una llamada firmada
  // real a cada exchange por cada conexión guardada en cada visita a la página.
  useEffect(() => {
    for (const connection of connections) {
      if (!(connection.id in balancesById) && !loadingIds.has(connection.id)) {
        fetchBalances(connection);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connections]);

  async function reloadConnections() {
    try {
      const responses = await Promise.all(EXCHANGES.map((e) => fetch(`/api/brokers/${e.value}/connections`)));
      const bodies = await Promise.all(responses.map((r) => r.json()));
      const failedIndex = responses.findIndex((r) => !r.ok);
      if (failedIndex !== -1) {
        setLoadError(typeof bodies[failedIndex].detail === "string" ? bodies[failedIndex].detail : "No se pudieron cargar tus conexiones.");
        return;
      }
      const merged = (bodies as Connection[][]).flat();
      merged.sort((a, b) => a.created_at.localeCompare(b.created_at));
      setConnections(merged);
      setLoadError(null);
    } catch {
      setLoadError("No se pudo conectar con la API.");
    }
  }

  async function createConnection() {
    setSaving(true);
    setSaveError(null);

    try {
      const response = await fetch(`/api/brokers/${exchange}/connections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret, passphrase: passphrase || undefined, label }),
      });
      const data = await response.json();
      if (!response.ok) {
        setSaveError(typeof data.detail === "string" ? data.detail : "No se pudo guardar la conexión.");
        return;
      }

      setApiKey("");
      setApiSecret("");
      setPassphrase("");
      setLabel("");
      await reloadConnections();
    } catch {
      setSaveError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteConnection(connection: Connection) {
    if (!confirm("¿Eliminar esta conexión?")) return;

    await fetch(`/api/brokers/${connection.exchange}/connections/${connection.id}`, { method: "DELETE" });
    if (expandedId === connection.id) setExpandedId(null);
    await reloadConnections();
  }

  function toggleBalances(connection: Connection) {
    if (expandedId === connection.id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(connection.id);
    if (!balancesById[connection.id] && !loadingIds.has(connection.id)) {
      fetchBalances(connection);
    }
  }

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

  function toggleTradingPanel(connection: Connection) {
    if (tradingConnectionId === connection.id) {
      setTradingConnectionId(null);
      return;
    }
    setTradingConnectionId(connection.id);
    if (!ordersById[connection.id]) {
      fetchOrders(connection);
    }
  }

  async function setTradingEnabled(connection: Connection, enabled: boolean) {
    setTogglingTradingId(connection.id);
    try {
      await fetch(`/api/brokers/${connection.exchange}/connections/${connection.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trading_enabled: enabled }),
      });
      await reloadConnections();
    } finally {
      setTogglingTradingId(null);
      setConfirmingConnection(null);
    }
  }

  function onTradingToggleClick(connection: Connection) {
    if (connection.trading_enabled) {
      // Apagar es la dirección segura: no hace falta el modal de confirmación.
      setTradingEnabled(connection, false);
    } else {
      setConfirmingConnection(connection);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Conexión con Exchanges</h1>
          <p className="text-sm text-muted">Guardá tus conexiones y consultá saldos cuando quieras</p>
        </div>
        <DataBadge live={connections.length > 0} label={connections.length > 0 ? "Cuentas conectadas" : "Sin conexiones"} />
      </div>

      <div className="rounded-3xl bg-panel p-8">
        <h2 className="text-lg font-bold text-ink">Conectar cuenta</h2>
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-3 text-xs text-muted">
          Usá una API key con permiso de <span className="font-semibold text-ink">solo lectura</span> (sin
          retiros ni trading). Probamos la conexión antes de guardarla: si las credenciales no funcionan, no se
          persiste nada.
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted">Exchange</span>
            <select
              value={exchange}
              onChange={(e) => setExchange(e.target.value)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
            >
              {EXCHANGES.map((e) => (
                <option key={e.value} value={e.value}>
                  {e.label}
                </option>
              ))}
            </select>
          </label>
          <TextField label="Nombre (opcional)" value={label} onChange={setLabel} placeholder="Ej: Cuenta principal" />
          <TextField label="API Key" value={apiKey} onChange={setApiKey} placeholder="Tu API key" />
          <TextField label="API Secret" value={apiSecret} onChange={setApiSecret} type="password" placeholder="Tu API secret" />
          {requiresPassphrase && (
            <TextField
              label="Passphrase"
              value={passphrase}
              onChange={setPassphrase}
              type="password"
              placeholder="Passphrase de tu API key"
            />
          )}
        </div>

        <button
          onClick={createConnection}
          disabled={saving || !apiKey || !apiSecret || (requiresPassphrase && !passphrase)}
          className="mt-6 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? "Conectando…" : "Conectar y guardar"}
        </button>

        {saveError && (
          <p className="mt-4 text-sm text-muted">
            <span className="font-semibold text-ink">No se pudo conectar: </span>
            {saveError}
          </p>
        )}
      </div>

      {loadError && (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudieron cargar tus conexiones: </span>
          {loadError}
        </div>
      )}

      {connections.length === 0 && !loadError && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          Todavía no conectaste ninguna cuenta.
        </div>
      )}

      {connections.length > 0 && (
        <div className="flex flex-col gap-4">
          {connections.map((connection) => (
            <div key={`${connection.exchange}-${connection.id}`} className="rounded-3xl bg-panel p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-ink">{connection.label}</h3>
                    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium text-muted">
                      {exchangeLabel(connection.exchange)}
                    </span>
                    {loadingIds.has(connection.id) && <span className="text-xs text-muted">Calculando saldo…</span>}
                    {typeof balancesById[connection.id]?.spot.usdt_total === "number" && (
                      <span className="rounded-full bg-surface px-2 py-0.5 text-xs font-semibold text-ink">
                        ≈ USD {formatUsdt(balancesById[connection.id].spot.usdt_total as number)}
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        connection.trading_enabled ? "bg-emerald-100 text-emerald-700" : "bg-surface text-muted"
                      }`}
                    >
                      {connection.trading_enabled ? "Trading habilitado" : "Solo lectura"}
                    </span>
                  </div>
                  <p className="text-xs text-muted">
                    Conectada el {new Date(connection.created_at).toLocaleDateString("es-AR")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => toggleBalances(connection)}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-ink"
                  >
                    {expandedId === connection.id ? "Ocultar saldos" : "Ver saldos"}
                  </button>
                  <button
                    onClick={() => toggleTradingPanel(connection)}
                    disabled={!connection.trading_enabled}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-ink disabled:opacity-40"
                  >
                    {tradingConnectionId === connection.id ? "Ocultar operar" : "Operar"}
                  </button>
                  <button
                    onClick={() => onTradingToggleClick(connection)}
                    disabled={togglingTradingId === connection.id}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted disabled:opacity-50"
                  >
                    {togglingTradingId === connection.id
                      ? "Actualizando…"
                      : connection.trading_enabled
                        ? "Deshabilitar trading"
                        : "Habilitar trading"}
                  </button>
                  <button
                    onClick={() => deleteConnection(connection)}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted"
                  >
                    Eliminar
                  </button>
                </div>
              </div>

              {expandedId === connection.id && (
                <div className="mt-6 border-t border-border pt-6">
                  {loadingIds.has(connection.id) && <p className="text-sm text-muted">Cargando saldos…</p>}
                  {balancesErrorById[connection.id] && (
                    <p className="text-sm text-muted">
                      <span className="font-semibold text-ink">No se pudieron cargar: </span>
                      {balancesErrorById[connection.id]}
                    </p>
                  )}
                  {balancesById[connection.id] && <BalancesPanel result={balancesById[connection.id]} />}
                </div>
              )}

              {tradingConnectionId === connection.id && connection.trading_enabled && (
                <TradingPanel
                  connection={connection}
                  symbols={symbols}
                  orders={ordersById[connection.id]}
                  ordersLoading={ordersLoadingId === connection.id}
                  ordersError={ordersErrorById[connection.id]}
                  onOrderPlaced={() => fetchOrders(connection)}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {confirmingConnection && (
        <EnableTradingModal
          connection={confirmingConnection}
          confirming={togglingTradingId === confirmingConnection.id}
          onCancel={() => setConfirmingConnection(null)}
          onConfirm={() => setTradingEnabled(confirmingConnection, true)}
        />
      )}
    </div>
  );
}
