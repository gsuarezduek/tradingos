import Link from "next/link";
import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { EXCHANGES } from "@/lib/exchanges";
import type { Connection } from "@/app/conexiones/ConexionesClient";
import type { SavedStrategySummary } from "@/app/estrategias/EstrategiasClient";
import { DashboardClient } from "./DashboardClient";

async function fetchConnections(token: string): Promise<{ connections: Connection[]; error: string | null }> {
  try {
    const responses = await Promise.all(
      EXCHANGES.map((exchange) =>
        fetch(`${API_BASE_URL}/brokers/${exchange.value}/connections`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(10000),
          cache: "no-store", // datos por usuario: nunca compartir esta respuesta entre requests
        }),
      ),
    );

    const bodies = await Promise.all(responses.map((r) => r.json()));
    const failedIndex = responses.findIndex((r) => !r.ok);
    if (failedIndex !== -1) {
      const failedBody = bodies[failedIndex];
      return {
        connections: [],
        error: typeof failedBody.detail === "string" ? failedBody.detail : "No se pudieron cargar tus conexiones.",
      };
    }

    const connections = (bodies as Connection[][]).flat();
    connections.sort((a, b) => a.created_at.localeCompare(b.created_at));
    return { connections, error: null };
  } catch {
    return { connections: [], error: "No se pudo conectar con la API." };
  }
}

async function fetchActiveStrategies(token: string): Promise<{ strategies: SavedStrategySummary[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategies`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        strategies: [],
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar tus estrategias.",
      };
    }
    return { strategies: (data as SavedStrategySummary[]).filter((s) => s.status === "active"), error: null };
  } catch {
    return { strategies: [], error: "No se pudo conectar con la API." };
  }
}

export default async function Home() {
  const token = await getSessionToken();

  if (!token) {
    return (
      <div className="rounded-3xl bg-panel p-12 text-center">
        <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted">
          Iniciá sesión para ver el capital total de tus cuentas conectadas y tus estrategias activas.
        </p>
        <Link
          href="/login"
          className="mt-6 inline-block rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white"
        >
          Iniciar sesión
        </Link>
      </div>
    );
  }

  const [{ connections, error: connectionsError }, { strategies: activeStrategies, error: strategiesError }] =
    await Promise.all([fetchConnections(token), fetchActiveStrategies(token)]);

  return (
    <DashboardClient
      initialConnections={connections}
      connectionsError={connectionsError}
      activeStrategies={activeStrategies}
      strategiesError={strategiesError}
    />
  );
}
