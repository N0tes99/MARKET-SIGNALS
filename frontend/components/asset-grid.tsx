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
  const { data: assets, isLoading, error } = useAssets();
  const { data: quotes } = useQuotes();

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
          Unable to connect to the API. Start the backend to see live data.
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
