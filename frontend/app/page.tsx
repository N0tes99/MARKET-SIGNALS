import { DashboardHeader } from "@/components/dashboard-header";
import { AlpacaActivityPanel } from "@/components/alpaca-activity-panel";
import { AssetGrid } from "@/components/asset-grid";
import { EquityOpportunitiesFeed } from "@/components/equity-opportunities-feed";
import { OpportunitiesFeed } from "@/components/opportunities-feed";
import { PaperAgentPanel } from "@/components/paper-agent-panel";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <DashboardHeader />
      <div className="container mx-auto px-4 pb-16 pt-2">
        <PaperAgentPanel />
        <AlpacaActivityPanel />
        <OpportunitiesFeed />
        <EquityOpportunitiesFeed />
        <AssetGrid />
      </div>
    </main>
  );
}
