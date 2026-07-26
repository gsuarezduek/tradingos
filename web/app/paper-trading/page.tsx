import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import type { SavedStrategySummary } from "@/app/constructor/ConstructorClient";
import { PaperTradingClient, type SessionSummary } from "./PaperTradingClient";

async function fetchSessions(token: string): Promise<{ sessions: SessionSummary[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/paper-trading/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store", // datos por usuario: nunca compartir esta respuesta entre requests
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        sessions: [],
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar tus sesiones.",
      };
    }
    return { sessions: data, error: null };
  } catch {
    return { sessions: [], error: "No se pudo conectar con la API." };
  }
}

// Estrategias guardadas del Constructor: paper trading siempre parte de una de estas
// (mismo endpoint que usa /constructor), no de un formulario armado desde cero.
async function fetchStrategies(token: string): Promise<{ strategies: SavedStrategySummary[]; error: string | null }> {
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
    return { strategies: data, error: null };
  } catch {
    return { strategies: [], error: "No se pudo conectar con la API." };
  }
}

export default async function PaperTradingPage() {
  const token = await getSessionToken();
  if (!token) {
    return (
      <PaperTradingClient
        initialSessions={[]}
        initialError="no autenticado"
        strategies={[]}
        strategiesError="no autenticado"
      />
    );
  }

  const [{ sessions, error }, { strategies, error: strategiesError }] = await Promise.all([
    fetchSessions(token),
    fetchStrategies(token),
  ]);
  return (
    <PaperTradingClient
      initialSessions={sessions}
      initialError={error}
      strategies={strategies}
      strategiesError={strategiesError}
    />
  );
}
