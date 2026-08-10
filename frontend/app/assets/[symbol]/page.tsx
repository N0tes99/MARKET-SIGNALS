import Link from "next/link";

import { AssetChartPanel } from "@/components/asset-chart-panel";
import { AssetPriceHeader } from "@/components/asset-price-header";
import { DecisionBanner } from "@/components/decision-banner";
import { DiscussionPanel } from "@/components/discussion-panel";
import { EvidencePanel } from "@/components/evidence-panel";
import { OutcomeLogger } from "@/components/outcome-logger";
import { EquitySetupsPanel } from "@/components/equity-setups-panel";
import { SetupIdeasPanel } from "@/components/setup-ideas-panel";
import { SiteHeader } from "@/components/site-header";

interface AssetDetailPageProps {
  params: Promise<{ symbol: string }>;
}

export default async function AssetDetailPage({ params }: AssetDetailPageProps) {
  const { symbol } = await params;
  const normalized = symbol.toUpperCase();

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <Link
          href="/"
          className="label-caps inline-flex text-muted-foreground/80 transition-colors hover:text-foreground"
        >
          ← back
        </Link>

        <header className="mt-6 border-b border-white/[0.06] pb-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h1 className="font-mono text-3xl font-light tracking-wide text-foreground">
              {normalized}
            </h1>
            <AssetPriceHeader symbol={normalized} />
          </div>
        </header>

        <div className="mt-6 space-y-6">
          <AssetChartPanel symbol={normalized} />
          <DecisionBanner symbol={normalized} />
          <SetupIdeasPanel symbol={normalized} />
          <EquitySetupsPanel symbol={normalized} />
          <OutcomeLogger symbol={normalized} />
          <DiscussionPanel symbol={normalized} />
          <EvidencePanel symbol={normalized} />
        </div>
      </div>
    </main>
  );
}
