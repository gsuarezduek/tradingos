import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { ConexionesClient, type Connection } from "./ConexionesClient";

async function fetchInitialConnections(): Promise<{ connections: Connection[]; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { connections: [], error: "no autenticado" };

  try {
    const response = await fetch(`${API_BASE_URL}/brokers/binance/connections`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store", // datos por usuario: nunca compartir esta respuesta entre requests
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        connections: [],
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar tus conexiones.",
      };
    }
    return { connections: data, error: null };
  } catch {
    return { connections: [], error: "No se pudo conectar con la API." };
  }
}

export default async function ConexionesPage() {
  const { connections, error } = await fetchInitialConnections();
  return <ConexionesClient initialConnections={connections} initialError={error} />;
}
