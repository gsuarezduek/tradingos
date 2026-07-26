import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/live-trading/sessions/${id}/stop`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
