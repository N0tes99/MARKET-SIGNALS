import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Signal Engine",
    short_name: "Signals",
    description: "Evidence-based market intelligence",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#06090c",
    theme_color: "#06090c",
    categories: ["finance", "business"],
    icons: [
      {
        src: "/apple-touch-icon.png?v=mark",
        sizes: "180x180",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-192.png?v=mark",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-512.png?v=mark",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-maskable-512.png?v=mark",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      {
        name: "Dashboard",
        short_name: "Home",
        url: "/",
        description: "Rankings and paper agent",
      },
      {
        name: "Radar",
        short_name: "Radar",
        url: "/radar",
        description: "Early, ignition, and running lists",
      },
      {
        name: "Tape",
        short_name: "Tape",
        url: "/tape",
        description: "Two-sided options hunt",
      },
      {
        name: "Perps",
        short_name: "Perps",
        url: "/perps",
        description: "Crypto perp paper, funding, liquidations",
      },
      {
        name: "Social",
        short_name: "Social",
        url: "/social",
        description: "Discussion feed",
      },
    ],
  };
}
