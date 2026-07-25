import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { EXCHANGES } from "@/lib/exchanges";
import { ConexionesClient, type Connection } from "./ConexionesClient";

async function fetchInitialConnections(): Promise<{ connections: Connection[]; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { connections: [], error: "no autenticado" };

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

export default async function ConexionesPage() {
  const { connections, error } = await fetchInitialConnections();
  return <ConexionesClient initialConnections={connections} initialError={error} />;
}
