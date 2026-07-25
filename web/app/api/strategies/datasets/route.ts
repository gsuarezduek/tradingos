import { API_BASE_URL } from "@/lib/api";

export async function GET() {
  const response = await fetch(`${API_BASE_URL}/strategies/datasets`, {
    signal: AbortSignal.timeout(10000),
    next: { revalidate: 300 },
  });
  const data = await response.json();
  return Response.json(data, { status: response.status });
}
