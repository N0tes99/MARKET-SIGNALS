import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Do not set output: "standalone" — that breaks Netlify's Next.js runtime.
  // Use standalone only if you containerize the frontend separately.
};

export default nextConfig;
