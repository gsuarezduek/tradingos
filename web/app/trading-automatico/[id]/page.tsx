import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { SessionDetailClient, type SessionDetail } from "./SessionDetailClient";

async function fetchSession(id: string): Promise<{ session: SessionDetail | null; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { session: null, error: "no autenticado" };

  try {
    const response = await fetch(`${API_BASE_URL}/live-trading/sessions/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        session: null,
        error: typeof data.detail === "string" ? data.detail : "No se pudo cargar la sesión.",
      };
    }
    return { session: data, error: null };
  } catch {
    return { session: null, error: "No se pudo conectar con la API." };
  }
}

export default async function LiveTradingSessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { session, error } = await fetchSession(id);
  return <SessionDetailClient sessionId={id} initialSession={session} initialError={error} />;
}
