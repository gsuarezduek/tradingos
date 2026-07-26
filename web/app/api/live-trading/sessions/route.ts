import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function GET() {
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/live-trading/sessions`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}

export async function POST(request: Request) {
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const body = await request.json();
  const response = await fetch(`${API_BASE_URL}/live-trading/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      strategy_id: body.strategy_id,
      broker_connection_id: body.broker_connection_id,
      symbol: body.symbol,
      timeframe: body.timeframe,
    }),
    signal: AbortSignal.timeout(20000), // corre el primer tick al toque, no solo crea el registro
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
