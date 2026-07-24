import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Chequeo optimista: solo mira si existe la cookie de sesión. La autorización real
// (firma y vigencia del JWT) siempre la valida el backend de Python en cada request a
// un endpoint protegido — esto es únicamente para no mostrar la página vacía y mandar
// derecho al login.
const COOKIE_NAME = "tradingos_session";

export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has(COOKIE_NAME);
  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/conexiones"],
};
