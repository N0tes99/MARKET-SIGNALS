import type { Metadata } from "next";
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

export const metadata: Metadata = {
  title: "Signal Engine",
  description: "Evidence-based market intelligence",
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
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
