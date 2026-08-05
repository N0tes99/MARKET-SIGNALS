"use client";

import { useMemo } from "react";

import { useAssets } from "@/hooks/use-assets";
import { useQuotes } from "@/hooks/use-quotes";
import { AssetCard } from "@/components/asset-card";
import { ASSET_SECTIONS, TRACKED_SYMBOLS } from "@/config/assets";
import type { AssetQuote, AssetSummary } from "@/services/api";

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

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="rounded-md border border-white/[0.06] bg-card/40 px-4 py-3">
          <p className="text-sm text-foreground/90">Loading market signals…</p>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            First load after idle can take up to ~1 minute (API cold start + ranking).
            {quotesLoading
              ? " Fetching live quotes in parallel…"
              : quotes
                ? ` Quotes ready for ${quotes.filter((q) => q.available).length} assets.`
                : ""}
          </p>
        </div>
        {ASSET_SECTIONS.map((section) => (
          <div key={section.label} className="space-y-3">
            <div className="h-4 w-20 animate-pulse rounded bg-muted" />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4">
              {section.symbols.map((symbol) => (
                <div key={symbol} className="surface h-52 animate-pulse" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
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

  const bySymbol = new Map(assets?.map((asset) => [asset.symbol, asset]) ?? []);

  return (
    <div className="space-y-10">
      {isFetching && (
        <p className="px-1 font-mono text-[11px] text-muted-foreground">
          Refreshing rankings in the background…
        </p>
      )}
      {ASSET_SECTIONS.map((section) => (
        <SectionGrid
          key={section.label}
          label={section.label}
          quotesBySymbol={quotesBySymbol}
          assets={section.symbols
            .map((symbol) => bySymbol.get(symbol))
            .filter((asset): asset is AssetSummary => asset !== undefined)}
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
