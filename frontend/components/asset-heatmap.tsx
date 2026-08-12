"use client";

import Link from "next/link";
import { useMemo } from "react";

import { heatmapWeight } from "@/config/assets";
import type { DashboardDensity } from "@/hooks/use-dashboard-view";
import { layoutTreemap } from "@/lib/treemap";
import { cn } from "@/lib/utils";
import type { AssetQuote, AssetSummary } from "@/services/api";

function heatDelta(asset: AssetSummary, quote?: AssetQuote | null): number | null {
  if (quote?.change_pct != null && Number.isFinite(quote.change_pct)) {
    return quote.change_pct;
  }
  if (asset.expected_value !== 0) {
    return asset.expected_value * 4;
  }
  if (asset.trend === "Bullish") return 1.2;
  if (asset.trend === "Bearish") return -1.2;
  if (asset.confidence > 0) return (asset.confidence - 50) / 12;
  return null;
}

function heatFill(delta: number | null): string {
  if (delta == null || Number.isNaN(delta)) return "rgba(255,255,255,0.05)";
  const t = Math.max(-1, Math.min(1, delta / 4));
  if (t >= 0) {
    const a = 0.16 + t * 0.7;
    return `rgba(143, 168, 138, ${a.toFixed(3)})`;
  }
  const a = 0.16 + -t * 0.7;
  return `rgba(166, 124, 124, ${a.toFixed(3)})`;
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}%`;
}

export function AssetHeatmap({
  assets,
  quotesBySymbol,
  density,
}: {
  assets: AssetSummary[];
  quotesBySymbol: Map<string, AssetQuote>;
  density: DashboardDensity;
}) {
  const cells = useMemo(() => {
    const laid = layoutTreemap(
      assets.map((asset) => ({ id: asset.symbol, value: heatmapWeight(asset.symbol) })),
    );
    const bySymbol = new Map(assets.map((asset) => [asset.symbol, asset]));
    return laid.map((cell) => {
      const asset = bySymbol.get(cell.id);
      const quote = quotesBySymbol.get(cell.id);
      const delta = asset ? heatDelta(asset, quote) : null;
      return { ...cell, asset, quote, delta };
    });
  }, [assets, quotesBySymbol]);

  const tall = density === "m";

  return (
    <div className="space-y-2">
      <div
        className="relative w-full overflow-hidden rounded-sm border border-white/[0.08] bg-[#0a0c10]"
        style={{ height: tall ? 380 : 240 }}
      >
        {cells.map((cell) => {
          if (!cell.asset) return null;
          const area = cell.w * cell.h;
          const showDelta = area > 70 && cell.delta != null;
          const showGrade = area > 45;
          const compact = area < 90;
          return (
            <Link
              key={cell.id}
              href={`/assets/${cell.asset.symbol}`}
              title={`${cell.asset.symbol} · ${cell.asset.trade_grade}${
                cell.delta != null ? ` · ${formatDelta(cell.delta)}` : ""
              }`}
              className={cn(
                "absolute box-border flex flex-col justify-end overflow-hidden border border-[#0a0c10] p-1.5 transition-[filter] hover:z-10 hover:brightness-125",
                compact ? "p-1" : "p-2",
              )}
              style={{
                left: `${cell.x}%`,
                top: `${cell.y}%`,
                width: `${cell.w}%`,
                height: `${cell.h}%`,
                backgroundColor: heatFill(cell.delta),
              }}
            >
              <p
                className={cn(
                  "font-mono font-medium leading-none tracking-wide text-foreground/95",
                  compact ? "text-[10px]" : "text-xs sm:text-sm",
                )}
              >
                {cell.asset.symbol}
              </p>
              {showGrade ? (
                <p className="mt-0.5 font-mono text-[10px] leading-none text-foreground/70">
                  {cell.asset.trade_grade}
                  {showDelta ? ` · ${formatDelta(cell.delta ?? 0)}` : ""}
                </p>
              ) : null}
            </Link>
          );
        })}
      </div>
      <p className="px-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
        Size ≈ market weight · green up / red down
      </p>
    </div>
  );
}
