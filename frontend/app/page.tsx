import { DashboardHeader } from "@/components/dashboard-header";
import { AlpacaActivityPanel } from "@/components/alpaca-activity-panel";
import { AssetGrid } from "@/components/asset-grid";
import { EquityOpportunitiesFeed } from "@/components/equity-opportunities-feed";
import { OpportunitiesFeed } from "@/components/opportunities-feed";
import { OptionsTapeStrip } from "@/components/options-tape-strip";
import { PaperAgentPanel } from "@/components/paper-agent-panel";
import { RadarPreviewStrip } from "@/components/radar-preview-strip";
import { TopPicks } from "@/components/top-picks";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <DashboardHeader />
      <div className="container mx-auto px-3 pb-12 pt-1 sm:px-4 sm:pb-16 sm:pt-2">
        <div className="desk-pair lg:grid lg:grid-cols-12 lg:gap-10">
          <div className="lg:col-span-7">
            <PaperAgentPanel />
          </div>
          <div className="lg:col-span-5">
            <TopPicks />
          </div>
        </div>
        <OptionsTapeStrip />
        <div className="desk-pair lg:grid lg:grid-cols-2 lg:gap-10">
          <EquityOpportunitiesFeed />
          <RadarPreviewStrip />
        </div>
        <AssetGrid />
        <div className="desk-pair lg:grid lg:grid-cols-2 lg:gap-10">
          <OpportunitiesFeed />
          <AlpacaActivityPanel />
        </div>
      </div>
    </main>
  );
}
