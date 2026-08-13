import dynamic from "next/dynamic";

import { DashboardHeader } from "@/components/dashboard-header";
import { AssetGrid } from "@/components/asset-grid";
import { DeferredMount } from "@/components/deferred-mount";
import { TopPicks } from "@/components/top-picks";

const PaperAgentPanel = dynamic(
  () =>
    import("@/components/paper-agent-panel").then((m) => m.PaperAgentPanel),
  { ssr: false, loading: () => null },
);
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

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <DashboardHeader />
      <div className="container mx-auto px-3 pb-12 pt-1 sm:px-4 sm:pb-16 sm:pt-2">
        {/* Primary surface first — rankings + quotes without competing cold feeds */}
        <TopPicks />
        <AssetGrid />

        <DeferredMount delayMs={150}>
          <PaperAgentPanel />
          <OptionsTapeStrip />
          <EquityOpportunitiesFeed />
          <RadarPreviewStrip />
          <OpportunitiesFeed />
          <AlpacaActivityPanel />
        </DeferredMount>
      </div>
    </main>
  );
}
