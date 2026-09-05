import type { NextConfig } from "next";

/**
 * Production security headers. CSP is set per-request in middleware.ts
 * (nonce + strict-dynamic for scripts). Do not also set CSP here — browsers
 * enforce every CSP header and a second static policy would break the nonce.
 */
const securityHeaders = [
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
