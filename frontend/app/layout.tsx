import type { Metadata, Viewport } from "next";
import { DM_Sans, IBM_Plex_Mono, Space_Grotesk, Syne } from "next/font/google";

import { Providers } from "@/components/providers";
import { VoidBackground } from "@/components/void-background";
import "./globals.css";

const sans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

const brand = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-brand",
  adjustFontFallback: false,
});

const rank = Syne({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-rank",
  // Metric overrides clip Syne’s deep single-story “g” descenders
  adjustFontFallback: false,
});

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#06090c" },
    { media: "(prefers-color-scheme: light)", color: "#06090c" },
  ],
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export const metadata: Metadata = {
  title: "Signal Engine",
  description: "Evidence-based market intelligence",
  applicationName: "Signal Engine",
  appleWebApp: {
    capable: true,
    title: "Signal Engine",
    statusBarStyle: "black-translucent",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${sans.variable} ${mono.variable} ${brand.variable} ${rank.variable} font-sans`}
      >
        <VoidBackground />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
