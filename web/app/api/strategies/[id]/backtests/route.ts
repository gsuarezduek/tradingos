import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const body = await request.json();
  const response = await fetch(`${API_BASE_URL}/strategies/${id}/backtests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(20000), // corre el backtest completo antes de responder
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
