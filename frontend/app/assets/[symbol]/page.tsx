import Link from "next/link";

import { AssetPriceHeader } from "@/components/asset-price-header";
import { DecisionBanner } from "@/components/decision-banner";
import { EvidencePanel } from "@/components/evidence-panel";
import { OutcomeLogger } from "@/components/outcome-logger";

interface AssetDetailPageProps {
  params: Promise<{ symbol: string }>;
}

export default async function AssetDetailPage({ params }: AssetDetailPageProps) {
  const { symbol } = await params;
  const normalized = symbol.toUpperCase();

  return (
    <main className="min-h-screen">
      <div className="container mx-auto px-4 py-10">
        <Link
          href="/"
          className="label-caps text-muted-foreground transition-colors hover:text-foreground"
        >
          ← back
        </Link>

        <header className="mt-8 border-b border-white/[0.06] pb-6">
          <p className="label-caps">Asset</p>
          <h1 className="mt-2 font-mono text-3xl font-light tracking-wide">{normalized}</h1>
          <AssetPriceHeader symbol={normalized} />
        </header>

        <DecisionBanner symbol={normalized} />
        <OutcomeLogger symbol={normalized} />
        <EvidencePanel symbol={normalized} />
      </div>
    </main>
  );
}
