import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "se_session";

const AUTH_PAGES = new Set([
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
  "/unlock",
  "/pending",
]);

function isPublicAsset(pathname: string): boolean {
  if (pathname.startsWith("/_next/")) return true;
  if (pathname.startsWith("/api/backend/api/v1/auth/")) return true;
  if (pathname.startsWith("/api/backend/api/v1/health")) return true;
  if (pathname.startsWith("/api/backend/api/v1/public/")) return true;
  if (pathname === "/favicon.svg" || pathname === "/favicon.ico") return true;
  return false;
}

/**
 * Soft UI gate: when NEXT_PUBLIC_REQUIRE_LOGIN=true, require se_session
 * before app surfaces. Pair with SITE_TOTP_SECRET on the API.
 */
export function middleware(request: NextRequest) {
  const requireLogin = process.env.NEXT_PUBLIC_REQUIRE_LOGIN === "true";
  const { pathname } = request.nextUrl;
  if (!requireLogin || isPublicAsset(pathname) || AUTH_PAGES.has(pathname)) {
    return NextResponse.next();
  }

  const session = request.cookies.get(SESSION_COOKIE)?.value;
  if (!session) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico)$).*)",
  ],
};
