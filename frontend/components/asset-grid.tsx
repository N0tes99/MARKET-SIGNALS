"use client";

import { useMemo } from "react";

import { useAssets } from "@/hooks/use-assets";
import { useQuotes } from "@/hooks/use-quotes";
import { AssetCard } from "@/components/asset-card";
import { ASSET_SECTIONS, TRACKED_SYMBOLS, type AssetClass } from "@/config/assets";
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
  };
}

function SectionGrid({
  label,
  assets,
  quotesBySymbol,
}: {
  label: string;
  assets: AssetSummary[];
  quotesBySymbol: Map<string, AssetQuote>;
}) {
  if (assets.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3">
      <h2 className="label-caps px-1 text-muted-foreground">{label}</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4">
        {assets.map((asset) => (
          <AssetCard
            key={asset.symbol}
            asset={asset}
            quote={quotesBySymbol.get(asset.symbol)}
          />
        ))}
      </div>
    </section>
  );
}

export function AssetGrid() {
  const { data: assets, isLoading, isFetching, error } = useAssets();
  const { data: quotes, isLoading: quotesLoading } = useQuotes();

  const quotesBySymbol = useMemo(() => {
    const map = new Map<string, AssetQuote>();
    for (const quote of quotes ?? []) {
      map.set(quote.symbol, quote);
    }
    return map;
  }, [quotes]);

  const bySymbol = useMemo(
    () => new Map(assets?.map((asset) => [asset.symbol, asset]) ?? []),
    [assets],
  );

  if (error && !assets) {
    return (
      <div className="surface p-10 text-center">
        <p className="text-sm text-muted-foreground">
          Unable to load asset rankings. The API may still be warming up — wait a minute and refresh.
        </p>
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {(isLoading || isFetching) && (
        <div className="rounded-md border border-white/[0.06] bg-card/40 px-4 py-3">
          <p className="text-sm text-foreground/90">
            {isLoading ? "Loading market signals…" : "Refreshing rankings in the background…"}
          </p>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            {isLoading
              ? "Showing tickers now; grades fill in when ranking finishes."
              : null}
            {quotesLoading
              ? " Fetching live quotes…"
              : quotes
                ? ` Quotes ready for ${quotes.filter((q) => q.available).length} assets.`
                : ""}
          </p>
        </div>
      )}
      {ASSET_SECTIONS.map((section) => (
        <SectionGrid
          key={section.label}
          label={section.label}
          quotesBySymbol={quotesBySymbol}
          assets={section.symbols.map(
            (symbol) =>
              bySymbol.get(symbol) ?? placeholderAsset(symbol, section.class),
          )}
        />
      ))}
      {assets && assets.length !== TRACKED_SYMBOLS.length && (
        <p className="px-1 font-mono text-xs text-muted-foreground">
          Showing {assets.length} of {TRACKED_SYMBOLS.length} tracked assets
        </p>
      )}
    </div>
  );
}
