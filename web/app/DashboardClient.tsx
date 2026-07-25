"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { ActiveStrategiesGrid } from "@/components/ActiveStrategiesGrid";
import { EXCHANGES } from "@/lib/exchanges";
import type { Connection } from "@/app/conexiones/ConexionesClient";
import type { SavedStrategySummary } from "@/app/constructor/ConstructorClient";

function exchangeLabel(value: string): string {
  return EXCHANGES.find((e) => e.value === value)?.label ?? value;
}

function formatUsd(value: number): string {
  return value.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

interface ConnectionBalanceState {
  usdtTotal: number | null; // null = todavía no se pudo calcular (error, o precios no disponibles)
  loading: boolean;
}

export function DashboardClient({
  initialConnections,
  connectionsError,
  activeStrategies,
  strategiesError,
}: {
  initialConnections: Connection[];
  connectionsError: string | null;
  activeStrategies: SavedStrategySummary[];
  strategiesError: string | null;
}) {
  const [balances, setBalances] = useState<Record<number, ConnectionBalanceState>>(() =>
    Object.fromEntries(initialConnections.map((c) => [c.id, { usdtTotal: null, loading: true }])),
  );

  // Igual que en Conexión con Exchanges: el total real requiere una llamada firmada a
  // cada exchange por cada cuenta guardada, así que se pide client-side apenas se
  // conoce la lista de conexiones (no bloquea el render inicial de la página).
  useEffect(() => {
    initialConnections.forEach((connection) => {
      fetch(`/api/brokers/${connection.exchange}/connections/${connection.id}/balances`)
        .then(async (response) => {
          const data = await response.json();
          const usdtTotal = response.ok && typeof data.spot?.usdt_total === "number" ? data.spot.usdt_total : null;
          setBalances((prev) => ({ ...prev, [connection.id]: { usdtTotal, loading: false } }));
        })
        .catch(() => {
          setBalances((prev) => ({ ...prev, [connection.id]: { usdtTotal: null, loading: false } }));
        });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stillLoading = Object.values(balances).some((b) => b.loading);
  const total = Object.values(balances).reduce((sum, b) => sum + (b.usdtTotal ?? 0), 0);
  const failedCount = Object.values(balances).filter((b) => !b.loading && b.usdtTotal === null).length;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Dashboard
            <InfoGuide>
              Capital total: suma el equivalente en USDT de los balances spot de todas tus cuentas conectadas
              (mismo cálculo que en Conexión con Exchanges). Estrategias activas: las que guardaste en el
              Constructor de Estrategias con estado &quot;Activa&quot;.
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">Vista general de tu operativa</p>
        </div>
        <DataBadge
          live={initialConnections.length > 0}
          label={initialConnections.length > 0 ? "Cuentas conectadas" : "Sin conexiones"}
        />
      </div>

      {connectionsError ? (
        <div className="rounded-3xl bg-panel p-8 text-sm text-muted">
          <span className="font-semibold text-ink">No se pudo cargar tu capital: </span>
          {connectionsError}
        </div>
      ) : (
        <div className="rounded-3xl bg-panel p-8">
          <span className="text-sm font-semibold text-ink">Capital total</span>
          {initialConnections.length === 0 ? (
            <p className="mt-3 text-sm text-muted">
              Todavía no conectaste ninguna cuenta.{" "}
              <Link href="/conexiones" className="font-semibold text-ink underline">
                Conectar una cuenta
              </Link>
            </p>
          ) : (
            <>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-4xl font-bold text-ink">${formatUsd(total)}</span>
                {stillLoading && <span className="text-xs text-muted">Calculando…</span>}
              </div>
              {!stillLoading && failedCount > 0 && (
                <p className="mt-2 text-xs text-muted">
                  {failedCount === 1
                    ? "No se pudo calcular el saldo de 1 cuenta; el total no la incluye."
                    : `No se pudo calcular el saldo de ${failedCount} cuentas; el total no las incluye.`}
                </p>
              )}
              <div className="mt-6 flex flex-wrap gap-3">
                {initialConnections.map((connection) => {
                  const b = balances[connection.id];
                  return (
                    <div key={connection.id} className="rounded-xl border border-border bg-surface px-4 py-2.5">
                      <div className="flex items-center gap-2 text-xs text-muted">
                        <span className="font-semibold text-ink">{connection.label}</span>
                        {exchangeLabel(connection.exchange)}
                      </div>
                      <div className="text-sm text-ink">
                        {b?.loading ? "…" : b?.usdtTotal !== null ? `$${formatUsd(b.usdtTotal!)}` : "—"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-ink">Estrategias activas</h2>
          <span className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted">
            {activeStrategies.length}
          </span>
        </div>
        {strategiesError ? (
          <div className="mt-4 rounded-3xl bg-panel p-8 text-sm text-muted">
            <span className="font-semibold text-ink">No se pudieron cargar tus estrategias: </span>
            {strategiesError}
          </div>
        ) : (
          <ActiveStrategiesGrid strategies={activeStrategies} />
        )}
      </div>
    </div>
  );
}
