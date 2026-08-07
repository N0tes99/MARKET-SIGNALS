"use client";

import Link from "next/link";

import type { DashboardDensity } from "@/hooks/use-dashboard-view";
import { cn } from "@/lib/utils";
import type { AssetQuote, AssetSummary } from "@/services/api";

function formatPrice(price: number): string {
  if (price >= 1000) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (price >= 1) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
  }
  return price.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 8,
  });
}

function formatChange(changePct: number): string {
  const sign = changePct > 0 ? "+" : "";
  return `${sign}${changePct.toFixed(2)}%`;
}

function changeClass(change: number | null | undefined): string {
  if (change == null) return "text-muted-foreground";
  if (change > 0) return "text-bullish";
  if (change < 0) return "text-bearish";
  return "text-neutral";
}

function trendAccent(trend: string): string {
  switch (trend) {
    case "Bullish":
      return "border-bullish/40 bg-bullish/10";
    case "Bearish":
      return "border-bearish/40 bg-bearish/10";
    default:
      return "border-white/[0.1] bg-white/[0.04]";
  }
}

function confidenceRing(confidence: number): string {
  if (confidence >= 65) return "ring-bullish/50";
  if (confidence > 0 && confidence <= 40) return "ring-bearish/40";
  return "ring-white/10";
}

export function AssetListRow({
  asset,
  quote,
  density,
  rank,
}: {
  asset: AssetSummary;
  quote?: AssetQuote | null;
  density: DashboardDensity;
  rank?: number;
}) {
  const change = quote?.change_pct;
  const compact = density === "s";

  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-white/[0.06] transition-[background-color] duration-200 hover:bg-white/[0.03]",
        compact ? "py-2" : "py-3",
      )}
    >
      {rank != null ? (
        <span
          className={cn(
            "w-7 shrink-0 text-sm",
            rank <= 3 ? "rank-num" : "rank-num-muted",
          )}
        >
          {rank}
        </span>
      ) : null}
      <Link
        href={`/assets/${asset.symbol}`}
        className={cn(
          "w-[4.5rem] shrink-0 font-mono tracking-wide text-foreground sm:w-20",
          compact ? "text-xs" : "text-sm",
        )}
      >
        {asset.symbol}
      </Link>
      <Link
        href={`/assets/${asset.symbol}`}
        className="flex min-w-0 flex-1 items-center justify-between gap-3"
      >
        <div className="min-w-0">
          <p className="truncate font-mono text-[11px] text-muted-foreground">
            {asset.asset_class} · {asset.trade_state.toLowerCase()}
          </p>
          {quote?.available && quote.price != null ? (
            <p className={cn("mt-0.5 font-mono", compact ? "text-xs" : "text-sm")}>
              <span className="text-foreground/90">${formatPrice(quote.price)}</span>
              {change != null ? (
                <span className={cn("ml-2 text-[11px]", changeClass(change))}>
                  {formatChange(change)}
                </span>
              ) : null}
            </p>
          ) : (
            <p className="mt-0.5 font-mono text-[11px] text-muted-foreground/70">price …</p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-right">
          <p className={cn("font-mono leading-none text-foreground/90", compact ? "text-xs" : "text-sm")}>
            {asset.trade_grade}
          </p>
          <p className="font-mono text-[10px] leading-none text-muted-foreground">
            {asset.confidence > 0 ? `${asset.confidence.toFixed(0)}%` : "—"}
          </p>
        </div>
      </Link>
    </div>
  );
}

export function AssetChip({
  asset,
  quote,
  density,
  rank,
}: {
  asset: AssetSummary;
  quote?: AssetQuote | null;
  density: DashboardDensity;
  rank?: number;
}) {
  const change = quote?.change_pct;
  const compact = density === "s";

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center border text-center transition-[transform,border-color,background-color] duration-200 hover:scale-[1.03]",
        trendAccent(asset.trend),
        "ring-1",
        confidenceRing(asset.confidence),
        compact
          ? "h-[4.75rem] w-[4.75rem] rounded-full px-1"
          : "h-[6.25rem] w-[6.25rem] rounded-full px-2",
      )}
    >
      {rank != null ? (
        <span
          className={cn(
            "absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full border border-white/[0.16] bg-[#0c0e12] px-1 text-[11px]",
            rank <= 3 ? "rank-num" : "rank-num-muted",
          )}
        >
          {rank}
        </span>
      ) : null}
      <Link href={`/assets/${asset.symbol}`} className="mt-0.5 block w-full px-1">
        <p
          className={cn(
            "font-mono tracking-wide text-foreground",
            compact ? "text-[11px]" : "text-sm",
          )}
        >
          {asset.symbol}
        </p>
        <p className={cn("font-mono text-foreground/90", compact ? "text-[10px]" : "text-xs")}>
          {asset.trade_grade}
        </p>
        {quote?.available && change != null ? (
          <p className={cn("font-mono", compact ? "text-[9px]" : "text-[10px]", changeClass(change))}>
            {formatChange(change)}
          </p>
        ) : quote?.available && quote.price != null ? (
          <p className={cn("font-mono text-muted-foreground", compact ? "text-[9px]" : "text-[10px]")}>
            ${formatPrice(quote.price)}
          </p>
        ) : null}
      </Link>
    </div>
  );
}
