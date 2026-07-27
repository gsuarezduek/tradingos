import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function GET() {
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/live-trading/risk-settings`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}

export async function PATCH(request: Request) {
  const token = await getSessionToken();
  if (!token) return Response.json({ detail: "no autenticado" }, { status: 401 });

  const body = await request.json();
  const response = await fetch(`${API_BASE_URL}/live-trading/risk-settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      daily_loss_limit_usdt: body.daily_loss_limit_usdt,
      weekly_loss_limit_usdt: body.weekly_loss_limit_usdt,
      max_exposure_per_asset_usdt: body.max_exposure_per_asset_usdt,
      max_exposure_per_strategy_usdt: body.max_exposure_per_strategy_usdt,
    }),
    signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
