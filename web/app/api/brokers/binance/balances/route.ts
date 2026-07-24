import { API_BASE_URL } from "@/lib/api";

// Proxy server-only hacia POST /brokers/binance/balances de la API de Python. Las
// credenciales viajan del browser a este server y de acá a la API; no se persisten ni
// se loguean en ningún punto de la cadena.
export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${API_BASE_URL}/brokers/binance/balances`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: body.api_key, api_secret: body.api_secret }),
    signal: AbortSignal.timeout(15000),
  });

  const data = await response.json();
  return Response.json(data, { status: response.status });
}
