import { API_BASE_URL } from "@/lib/api";

// Proxy server-only hacia POST /backtests de la API de Python. Fija strategy/dataset
// acá (no los elige el cliente): hoy solo existe ma_crossover sobre BTCUSDT_1h.parquet
// deployado, así que no tiene sentido exponer esos campos como configurables todavía.
export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${API_BASE_URL}/backtests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      strategy: "ma_crossover",
      dataset: "BTCUSDT_1h.parquet",
      config: body.config,
      initial_equity: body.initial_equity,
    }),
    signal: AbortSignal.timeout(20000),
  });

  const data = await response.json();
  return Response.json(data, { status: response.status });
}
