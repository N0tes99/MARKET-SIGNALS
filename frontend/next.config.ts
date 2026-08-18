import type { NextConfig } from "next";

/**
 * Production CSP for the Netlify app. next/font is self-hosted at build time.
 * 'unsafe-inline' is required for Next.js App Router hydration (no nonce yet).
 * API calls in production go through same-origin /api/backend.
 */
function contentSecurityPolicy(): string {
  const connect = ["'self'"];
  if (process.env.NODE_ENV !== "production") {
    connect.push("http://localhost:8000", "http://127.0.0.1:8000");
  }
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src ${connect.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ].join("; ");
}

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy() },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not set output: "standalone" — that breaks Netlify's Next.js runtime.
  // Use standalone only if you containerize the frontend separately.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
