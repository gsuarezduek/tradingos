import { API_BASE_URL } from "@/lib/api";
import { setSessionCookie } from "@/lib/session";

export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
    signal: AbortSignal.timeout(10000),
  });

  const data = await response.json();
  if (!response.ok) {
    return Response.json(data, { status: response.status });
  }

  await setSessionCookie(data.access_token);
  return Response.json({ ok: true });
}
