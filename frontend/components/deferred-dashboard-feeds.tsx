"use client";

import dynamic from "next/dynamic";

import { DeferredMount } from "@/components/deferred-mount";

const OptionsTapeStrip = dynamic(
  () =>
    import("@/components/options-tape-strip").then((m) => m.OptionsTapeStrip),
  { ssr: false, loading: () => null },
);
const EquityOpportunitiesFeed = dynamic(
  () =>
    import("@/components/equity-opportunities-feed").then(
      (m) => m.EquityOpportunitiesFeed,
    ),
  { ssr: false, loading: () => null },
);
const RadarPreviewStrip = dynamic(
  () =>
    import("@/components/radar-preview-strip").then((m) => m.RadarPreviewStrip),
  { ssr: false, loading: () => null },
);
const OpportunitiesFeed = dynamic(
  () =>
    import("@/components/opportunities-feed").then((m) => m.OpportunitiesFeed),
  { ssr: false, loading: () => null },
);
const AlpacaActivityPanel = dynamic(
  () =>
    import("@/components/alpaca-activity-panel").then(
      (m) => m.AlpacaActivityPanel,
    ),
  { ssr: false, loading: () => null },
);

/**
 * Secondary home strips. Loaded from a Client Component so `ssr: false`
 * is valid (Next.js forbids that option in Server Components).
 */
export function DeferredDashboardFeeds() {
  return (
    <DeferredMount delayMs={150}>
      <OptionsTapeStrip />
      <div className="desk-pair lg:grid lg:grid-cols-2 lg:gap-10">
        <EquityOpportunitiesFeed />
        <RadarPreviewStrip />
      </div>
      <div className="desk-pair lg:grid lg:grid-cols-2 lg:gap-10">
        <OpportunitiesFeed />
        <AlpacaActivityPanel />
      </div>
    </DeferredMount>
  );
}
