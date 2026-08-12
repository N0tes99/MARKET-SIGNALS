"use client";

import Link from "next/link";
import { useLayoutEffect, useMemo, useRef, useState } from "react";

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
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: 360, h: 200 });

  useLayoutEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const sync = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) setBox({ w: width, h: height });
    };
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const aspect = box.w / box.h;
  const cells = useMemo(() => {
    const laid = layoutTreemap(
      assets.map((asset) => ({ id: asset.symbol, value: heatmapWeight(asset.symbol) })),
      aspect,
    );
    const bySymbol = new Map(assets.map((asset) => [asset.symbol, asset]));
    return laid.map((cell) => {
      const asset = bySymbol.get(cell.id);
      const quote = quotesBySymbol.get(cell.id);
      const delta = asset ? heatDelta(asset, quote) : null;
      return { ...cell, asset, quote, delta };
    });
  }, [aspect, assets, quotesBySymbol]);

  const tall = density === "m";

  return (
    <div className="space-y-1.5">
      <div
        ref={boxRef}
        className={cn(
          "relative w-full overflow-hidden rounded-sm border border-white/[0.08] bg-[#0a0c10]",
          "h-[12.5rem]",
          "sm:h-[220px]",
          tall && "sm:h-[360px]",
        )}
      >
        {cells.map((cell) => {
          if (!cell.asset) return null;
          const pxW = (cell.w / 100) * box.w;
          const pxH = (cell.h / 100) * box.h;
          const showTicker = pxW >= 26 && pxH >= 11;
          const showGrade = pxW >= 34 && pxH >= 22;
          const showDelta = pxW >= 48 && pxH >= 30 && cell.delta != null;
          const compact = pxW < 56 || pxH < 36;
          return (
            <Link
              key={cell.id}
              href={`/assets/${cell.asset.symbol}`}
              title={`${cell.asset.symbol} · ${cell.asset.trade_grade}${
                cell.delta != null ? ` · ${formatDelta(cell.delta)}` : ""
              }`}
              className={cn(
                "absolute box-border flex flex-col items-center justify-center overflow-hidden border border-[#0a0c10] text-center transition-[filter] hover:z-10 hover:brightness-125",
                compact ? "px-0.5 py-px" : "p-1 sm:p-1.5",
              )}
              style={{
                left: `${cell.x}%`,
                top: `${cell.y}%`,
                width: `${cell.w}%`,
                height: `${cell.h}%`,
                backgroundColor: heatFill(cell.delta),
              }}
            >
              {showTicker ? (
                <p
                  className={cn(
                    "font-mono font-semibold leading-none tracking-wide text-foreground/95",
                    compact ? "text-[11px] sm:text-[10px]" : "text-[12px] sm:text-xs",
                  )}
                >
                  {cell.asset.symbol}
                </p>
              ) : null}
              {showGrade ? (
                <p className="mt-0.5 font-mono text-[10px] leading-none text-foreground/65 sm:text-[10px]">
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
