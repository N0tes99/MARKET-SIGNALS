"use client";

import { useMemo } from "react";

import { compareByScore, SectionBody } from "@/components/asset-grid";
import { ASSET_SECTIONS, TRACKED_SYMBOLS, type AssetClass } from "@/config/assets";
import { useAssets } from "@/hooks/use-assets";
import { useDashboardView } from "@/hooks/use-dashboard-view";
import { useQuotes } from "@/hooks/use-quotes";
import type { AssetQuote, AssetSummary } from "@/services/api";

function placeholderAsset(symbol: string, assetClass: AssetClass): AssetSummary {
  return {
    symbol,
    confidence: 0,
    trend: "Neutral",
    trade_grade: "—",
    buyer_strength: 0,
    risk: 0,
    expected_value: 0,
    trade_state: "LOADING",
    execution_signal: "…",
    asset_class: assetClass,
    data_degraded: false,
  };
}

function isPlaceholder(asset: AssetSummary): boolean {
  return asset.trade_state === "LOADING" || asset.trade_grade === "—";
}

export function TopPicks() {
  const { data } = useAssets();
  const assets = data?.assets;
  const { data: quotes } = useQuotes();
  const { layout, density } = useDashboardView();

  const quotesBySymbol = useMemo(() => {
    const map = new Map<string, AssetQuote>();
    for (const quote of quotes ?? []) {
      map.set(quote.symbol, quote);
    }
    return map;
  }, [quotes]);

  const topPicks = useMemo(() => {
    const bySymbol = new Map(assets?.map((asset) => [asset.symbol, asset]) ?? []);
    return TRACKED_SYMBOLS.map((symbol) => {
      const known = bySymbol.get(symbol);
      if (known) return known;
      const section = ASSET_SECTIONS.find((s) =>
        (s.symbols as readonly string[]).includes(symbol),
      );
      return placeholderAsset(symbol, section?.class ?? "stock");
    })
      .filter((asset) => !isPlaceholder(asset))
      .sort(compareByScore)
      .slice(0, 8);
  }, [assets]);

  if (topPicks.length === 0) return null;

  return (
    <section className="mb-6 border-b border-white/[0.05] pb-6 sm:mb-8 sm:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-1">
        <h2 className="label-caps text-muted-foreground">Top picks</h2>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          Ranked by confidence
        </p>
      </div>
      <div className="mt-3">
        <SectionBody
          assets={topPicks}
          quotesBySymbol={quotesBySymbol}
          layout={layout}
          density={density}
          showRank
          emphasizeFirst
        />
      </div>
    </section>
  );
}
