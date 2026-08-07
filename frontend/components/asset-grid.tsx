"use client";

import { useMemo } from "react";

import { AssetCard } from "@/components/asset-card";
import { AssetChip, AssetListRow } from "@/components/asset-view-items";
import { DashboardViewControls } from "@/components/dashboard-view-controls";
import { ASSET_SECTIONS, TRACKED_SYMBOLS, type AssetClass } from "@/config/assets";
import { useAssets } from "@/hooks/use-assets";
import { useDashboardView } from "@/hooks/use-dashboard-view";
import { useQuotes } from "@/hooks/use-quotes";
import { cn } from "@/lib/utils";
import type { AssetQuote, AssetSummary } from "@/services/api";

const GRADE_RANK: Record<string, number> = {
  "A+": 6,
  A: 5,
  B: 4,
  C: 3,
  D: 2,
  F: 1,
  "—": 0,
};

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

/** Higher confidence, then EV, then grade — placeholders sink to the bottom. */
export function compareByScore(a: AssetSummary, b: AssetSummary): number {
  const aPending = isPlaceholder(a);
  const bPending = isPlaceholder(b);
  if (aPending !== bPending) return aPending ? 1 : -1;
  if (b.confidence !== a.confidence) return b.confidence - a.confidence;
  if (b.expected_value !== a.expected_value) return b.expected_value - a.expected_value;
  return (GRADE_RANK[b.trade_grade] ?? 0) - (GRADE_RANK[a.trade_grade] ?? 0);
}

function SectionBody({
  assets,
  quotesBySymbol,
  layout,
  density,
  showRank,
  emphasizeFirst,
}: {
  assets: AssetSummary[];
  quotesBySymbol: Map<string, AssetQuote>;
  layout: "list" | "chips" | "grid";
  density: "s" | "m";
  showRank: boolean;
  emphasizeFirst?: boolean;
}) {
  if (layout === "list") {
    return (
      <div key={layout} className="surface motion-view-pane motion-stagger px-3 sm:px-4">
        {assets.map((asset, index) => (
          <div
            key={asset.symbol}
            className={cn(emphasizeFirst && index === 0 && "motion-rank-1 rounded-sm")}
          >
            <AssetListRow
              asset={asset}
              quote={quotesBySymbol.get(asset.symbol)}
              density={density}
              rank={showRank ? index + 1 : undefined}
            />
          </div>
        ))}
      </div>
    );
  }

  if (layout === "chips") {
    return (
      <div
        key={layout}
        className={cn(
          "motion-view-pane motion-stagger flex flex-wrap",
          density === "s" ? "gap-2" : "gap-3",
        )}
      >
        {assets.map((asset, index) => (
          <div
            key={asset.symbol}
            className={cn(emphasizeFirst && index === 0 && "rounded-full motion-rank-1")}
          >
            <AssetChip
              asset={asset}
              quote={quotesBySymbol.get(asset.symbol)}
              density={density}
              rank={showRank ? index + 1 : undefined}
            />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div
      key={layout}
      className={cn(
        "motion-view-pane motion-stagger grid gap-3",
        density === "s"
          ? "sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5"
          : "sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4",
      )}
    >
      {assets.map((asset, index) => (
        <div
          key={asset.symbol}
          className={cn(emphasizeFirst && index === 0 && "rounded-lg motion-rank-1")}
        >
          <AssetCard
            asset={asset}
            quote={quotesBySymbol.get(asset.symbol)}
            density={density}
            rank={showRank ? index + 1 : undefined}
          />
        </div>
      ))}
    </div>
  );
}

export function AssetGrid() {
  const { data: assets, isLoading, isFetching, error } = useAssets();
  const { data: quotes, isLoading: quotesLoading } = useQuotes();
  const { layout, density, setLayout, setDensity, ready } = useDashboardView();

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

  const rankedAll = useMemo(() => {
    const list = TRACKED_SYMBOLS.map((symbol) => {
      const known = bySymbol.get(symbol);
      if (known) return known;
      const section = ASSET_SECTIONS.find((s) =>
        (s.symbols as readonly string[]).includes(symbol),
      );
      return placeholderAsset(symbol, section?.class ?? "stock");
    });
    return [...list].sort(compareByScore);
  }, [bySymbol]);

  const topPicks = useMemo(
    () => rankedAll.filter((a) => !isPlaceholder(a)).slice(0, 8),
    [rankedAll],
  );

  if (error && !assets) {
    const message = error instanceof Error ? error.message : "Unknown error";
    const timedOut =
      /504|502|timed out|timeout/i.test(message);
    return (
      <div className="surface p-10 text-center">
        <p className="text-sm text-muted-foreground">
          {timedOut
            ? "Rankings timed out while the API was cold. Quotes above still work — refresh once, or wait a few minutes for keep-warm and try again."
            : "Unable to load asset rankings. The API may still be warming up — wait a minute and refresh."}
        </p>
        <p className="mt-2 font-mono text-xs text-muted-foreground">{message}</p>
        <button
          type="button"
          className="mt-4 text-sm text-foreground underline underline-offset-4"
          onClick={() => window.location.reload()}
        >
          Refresh now
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {ready ? (
        <DashboardViewControls
          layout={layout}
          density={density}
          onLayout={setLayout}
          onDensity={setDensity}
        />
      ) : (
        <div className="h-10 border-b border-white/[0.06]" />
      )}

      {(isLoading || isFetching) && (
        <div className="status-line px-1 py-1">
          <span className="idle-dot" />
          <span>
            {isLoading
              ? "ranking…"
              : "refreshing…"}
            {!quotesLoading && quotes
              ? ` · ${quotes.filter((q) => q.available).length} quotes`
              : quotesLoading
                ? " · quotes…"
                : ""}
          </span>
        </div>
      )}

      {topPicks.length > 0 ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2 px-1">
            <h2 className="label-caps text-muted-foreground">Top picks</h2>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Ranked by confidence
            </p>
          </div>
          <SectionBody
            assets={topPicks}
            quotesBySymbol={quotesBySymbol}
            layout={layout}
            density={density}
            showRank
            emphasizeFirst
          />
        </section>
      ) : null}

      {ASSET_SECTIONS.map((section) => {
        const sectionAssets = [...section.symbols]
          .map(
            (symbol) =>
              bySymbol.get(symbol) ?? placeholderAsset(symbol, section.class),
          )
          .sort(compareByScore);

        return (
          <section key={section.label} className="space-y-3">
            <h2 className="label-caps px-1 text-muted-foreground">{section.label}</h2>
            <SectionBody
              assets={sectionAssets}
              quotesBySymbol={quotesBySymbol}
              layout={layout}
              density={density}
              showRank
            />
          </section>
        );
      })}

      {assets && assets.length !== TRACKED_SYMBOLS.length && (
        <p className="px-1 font-mono text-xs text-muted-foreground">
          Showing {assets.length} of {TRACKED_SYMBOLS.length} tracked assets
        </p>
      )}
    </div>
  );
}
