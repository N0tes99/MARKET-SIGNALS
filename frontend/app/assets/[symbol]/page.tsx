import Link from "next/link";

import { DecisionBanner } from "@/components/decision-banner";
import { EvidencePanel } from "@/components/evidence-panel";

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

        <header className="mt-8 border-b border-border pb-6">
          <p className="label-caps">Asset</p>
          <h1 className="mt-2 font-mono text-3xl font-light tracking-wide">{normalized}</h1>
        </header>

        <DecisionBanner symbol={normalized} />
        <EvidencePanel symbol={normalized} />
      </div>
    </main>
  );
}
