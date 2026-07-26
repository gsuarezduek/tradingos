import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function GET(request: Request, ctx: { params: Promise<{ exchange: string; id: string }> }) {
  const { exchange, id } = await ctx.params;
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/brokers/${exchange}/connections/${id}/orders`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}

export async function POST(request: Request, ctx: { params: Promise<{ exchange: string; id: string }> }) {
  const { exchange, id } = await ctx.params;
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const body = await request.json();
  const response = await fetch(`${API_BASE_URL}/brokers/${exchange}/connections/${id}/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
