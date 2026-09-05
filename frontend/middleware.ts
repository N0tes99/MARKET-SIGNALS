import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Per-request CSP nonce. Next.js App Router needs a nonce (or 'unsafe-inline')
 * for hydration scripts. 'strict-dynamic' + nonce is the workaround: modern
 * browsers ignore 'unsafe-inline' for scripts; styles still allow inline
 * (Tailwind / Next). Social posts remain React text, not HTML.
 */
function contentSecurityPolicy(nonce: string): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'unsafe-inline'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "frame-src 'none'",
    "upgrade-insecure-requests",
  ].join("; ");
}

export function middleware(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  // Dev must not ship CSP: React Refresh uses eval. Production gets nonce +
  // strict-dynamic so 'unsafe-inline' on script-src is ignored by CSP3.
  if (process.env.NODE_ENV === "production") {
    requestHeaders.set("Content-Security-Policy", csp);
  }
  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });
  if (process.env.NODE_ENV === "production") {
    response.headers.set("Content-Security-Policy", csp);
  }
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
