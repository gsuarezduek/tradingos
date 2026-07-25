import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { PaperTradingClient, type SessionDetail } from "./PaperTradingClient";

async function fetchCurrentSession(): Promise<{ session: SessionDetail | null; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { session: null, error: "no autenticado" };

  try {
    const listResponse = await fetch(`${API_BASE_URL}/paper-trading/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store", // datos por usuario: nunca compartir esta respuesta entre requests
    });
    const list = await listResponse.json();
    if (!listResponse.ok) {
      return {
        session: null,
        error: typeof list.detail === "string" ? list.detail : "No se pudieron cargar tus sesiones.",
      };
    }
    if (list.length === 0) return { session: null, error: null };

    const detailResponse = await fetch(`${API_BASE_URL}/paper-trading/sessions/${list[0].id}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const detail = await detailResponse.json();
    if (!detailResponse.ok) {
      return {
        session: null,
        error: typeof detail.detail === "string" ? detail.detail : "No se pudo cargar el detalle de la sesión.",
      };
    }
    return { session: detail, error: null };
  } catch {
    return { session: null, error: "No se pudo conectar con la API." };
  }
}

export default async function PaperTradingPage() {
  const { session, error } = await fetchCurrentSession();
  return <PaperTradingClient initialSession={session} initialError={error} />;
}
