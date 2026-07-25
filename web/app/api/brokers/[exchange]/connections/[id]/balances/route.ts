import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function GET(request: Request, ctx: { params: Promise<{ exchange: string; id: string }> }) {
  const { exchange, id } = await ctx.params;
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/brokers/${exchange}/connections/${id}/balances`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
