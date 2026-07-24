"use client";

import { useState } from "react";
import { DataBadge } from "@/components/DataBadge";

interface SpotBalance {
  asset: string;
  free: number;
  locked: number;
  total: number;
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
}

interface BinanceBalancesResponse {
  spot: SectionResult<SpotBalance>;
  futures_usdm: SectionResult<FuturesBalance>;
}

export interface Connection {
  id: number;
  label: string;
  created_at: string;
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

function BalancesPanel({ result }: { result: BinanceBalancesResponse }) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
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
                  <th className="pb-2 font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {result.spot.balances.map((b) => (
                  <tr key={b.asset} className="border-b border-border last:border-0">
                    <td className="py-2 pr-4 font-semibold text-ink">{b.asset}</td>
                    <td className="py-2 pr-4 text-ink">{b.free.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                    <td className="py-2 pr-4 text-ink">{b.locked.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                    <td className="py-2 text-ink">{b.total.toLocaleString("es-AR", { maximumFractionDigits: 8 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

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
    </div>
  );
}

export function ConexionesClient({
  initialConnections,
  initialError,
}: {
  initialConnections: Connection[];
  initialError: string | null;
}) {
  const [connections, setConnections] = useState<Connection[]>(initialConnections);
  const [loadError, setLoadError] = useState<string | null>(initialError);

  const [label, setLabel] = useState("Binance");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [balancesById, setBalancesById] = useState<Record<number, BinanceBalancesResponse>>({});
  const [balancesLoadingId, setBalancesLoadingId] = useState<number | null>(null);
  const [balancesErrorById, setBalancesErrorById] = useState<Record<number, string>>({});

  async function reloadConnections() {
    try {
      const response = await fetch("/api/brokers/binance/connections");
      const data = await response.json();
      if (!response.ok) {
        setLoadError(typeof data.detail === "string" ? data.detail : "No se pudieron cargar tus conexiones.");
        return;
      }
      setConnections(data);
      setLoadError(null);
    } catch {
      setLoadError("No se pudo conectar con la API.");
    }
  }

  async function createConnection() {
    setSaving(true);
    setSaveError(null);

    try {
      const response = await fetch("/api/brokers/binance/connections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret, label }),
      });
      const data = await response.json();
      if (!response.ok) {
        setSaveError(typeof data.detail === "string" ? data.detail : "No se pudo guardar la conexión.");
        return;
      }

      setApiKey("");
      setApiSecret("");
      setLabel("Binance");
      await reloadConnections();
    } catch {
      setSaveError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteConnection(id: number) {
    if (!confirm("¿Eliminar esta conexión?")) return;

    await fetch(`/api/brokers/binance/connections/${id}`, { method: "DELETE" });
    if (expandedId === id) setExpandedId(null);
    await reloadConnections();
  }

  async function toggleBalances(id: number) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(id);
    if (balancesById[id]) return;

    setBalancesLoadingId(id);
    try {
      const response = await fetch(`/api/brokers/binance/connections/${id}/balances`);
      const data = await response.json();
      if (!response.ok) {
        setBalancesErrorById((prev) => ({
          ...prev,
          [id]: typeof data.detail === "string" ? data.detail : "No se pudieron cargar los saldos.",
        }));
        return;
      }
      setBalancesById((prev) => ({ ...prev, [id]: data }));
    } catch {
      setBalancesErrorById((prev) => ({ ...prev, [id]: "No se pudo conectar con la API." }));
    } finally {
      setBalancesLoadingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Conexión con Exchanges</h1>
          <p className="text-sm text-muted">Guardá tus conexiones de Binance y consultá saldos cuando quieras</p>
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
          <TextField label="Nombre" value={label} onChange={setLabel} placeholder="Ej: Cuenta principal" />
          <TextField label="API Key" value={apiKey} onChange={setApiKey} placeholder="Tu API key de Binance" />
          <TextField
            label="API Secret"
            value={apiSecret}
            onChange={setApiSecret}
            type="password"
            placeholder="Tu API secret de Binance"
          />
        </div>

        <button
          onClick={createConnection}
          disabled={saving || !apiKey || !apiSecret}
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
            <div key={connection.id} className="rounded-3xl bg-panel p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-bold text-ink">{connection.label}</h3>
                  <p className="text-xs text-muted">
                    Conectada el {new Date(connection.created_at).toLocaleDateString("es-AR")}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => toggleBalances(connection.id)}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-ink"
                  >
                    {expandedId === connection.id ? "Ocultar saldos" : "Ver saldos"}
                  </button>
                  <button
                    onClick={() => deleteConnection(connection.id)}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-muted"
                  >
                    Eliminar
                  </button>
                </div>
              </div>

              {expandedId === connection.id && (
                <div className="mt-6 border-t border-border pt-6">
                  {balancesLoadingId === connection.id && <p className="text-sm text-muted">Cargando saldos…</p>}
                  {balancesErrorById[connection.id] && (
                    <p className="text-sm text-muted">
                      <span className="font-semibold text-ink">No se pudieron cargar: </span>
                      {balancesErrorById[connection.id]}
                    </p>
                  )}
                  {balancesById[connection.id] && <BalancesPanel result={balancesById[connection.id]} />}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
