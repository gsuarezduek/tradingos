import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { PaperTradingClient, type SessionSummary } from "./PaperTradingClient";

async function fetchSessions(): Promise<{ sessions: SessionSummary[]; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { sessions: [], error: "no autenticado" };

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

// Lista de símbolos de Binance para el autocomplete; si falla, el formulario sigue
// funcionando con texto libre (no bloqueamos la creación de sesiones por esto).
async function fetchSymbols(): Promise<string[]> {
  const token = await getSessionToken();
  if (!token) return [];

  try {
    const response = await fetch(`${API_BASE_URL}/paper-trading/symbols`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(15000),
      cache: "no-store",
    });
    if (!response.ok) return [];
    return await response.json();
  } catch {
    return [];
  }
}

export default async function PaperTradingPage() {
  const [{ sessions, error }, symbols] = await Promise.all([fetchSessions(), fetchSymbols()]);
  return <PaperTradingClient initialSessions={sessions} initialError={error} symbols={symbols} />;
}
