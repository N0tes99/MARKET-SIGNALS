"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchCandles } from "@/services/api";
import { cn } from "@/lib/utils";

const MiniSparkline = dynamic(
  () =>
    import("@/components/mini-sparkline").then((mod) => mod.MiniSparkline),
  {
    ssr: false,
    loading: () => (
      <p className="pt-8 text-center font-mono text-[10px] text-muted-foreground">
        Loading…
      </p>
    ),
  },
);

interface TickerMiniChartProps {
  symbol: string;
  className?: string;
  size?: "sm" | "md";
}

export function TickerMiniChart({ symbol, className, size = "md" }: TickerMiniChartProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const candlesQuery = useQuery({
    queryKey: ["candles", symbol, "15m"],
    queryFn: () => fetchCandles(symbol, "15m", 32),
    enabled: open,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });

  const points =
    candlesQuery.data?.candles.map((c) => ({
      t: c.t,
      close: c.c,
    })) ?? [];

  const first = points[0]?.close;
  const last = points[points.length - 1]?.close;
  const up = first != null && last != null ? last >= first : true;
  const stroke = up ? "#8fa88a" : "#a67c7c";
  const fill = up ? "rgba(143,168,138,0.2)" : "rgba(166,124,124,0.2)";

  return (
    <div
      ref={rootRef}
      className={cn("relative inline-flex", className)}
      onMouseEnter={(e) => e.stopPropagation()}
      onMouseLeave={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onMouseEnter={(e) => e.stopPropagation()}
        className={cn(
          "font-mono tracking-wide text-foreground",
          size === "sm" ? "text-xs" : "text-lg",
          open && "text-foreground underline underline-offset-4",
        )}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Show ${symbol} 15 minute chart`}
        title="Click for 15m chart"
      >
        {symbol}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={`${symbol} 15 minute chart`}
          className="absolute left-0 top-full z-40 mt-2 w-[220px] border border-white/[0.1] bg-[#0c0e12]/95 p-3 shadow-xl backdrop-blur-md"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
        >
          <div className="flex items-baseline justify-between gap-2">
            <p className="font-mono text-xs text-foreground">{symbol}</p>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              15m
            </p>
          </div>

          <div className="mt-2 h-[88px] w-full pointer-events-none">
            {candlesQuery.isLoading ? (
              <p className="pt-8 text-center font-mono text-[10px] text-muted-foreground">
                Loading…
              </p>
            ) : null}
            {candlesQuery.isError ? (
              <p className="pt-8 text-center text-[11px] text-bearish">Chart unavailable</p>
            ) : null}
            {!candlesQuery.isLoading && !candlesQuery.isError && points.length === 0 ? (
              <p className="pt-8 text-center font-mono text-[10px] text-muted-foreground">
                No bars
              </p>
            ) : null}
            {points.length > 0 ? (
              <MiniSparkline points={points} stroke={stroke} fill={fill} />
            ) : null}
          </div>

          <Link
            href={`/assets/${symbol}`}
            className="mt-2 block font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
            onClick={(e) => e.stopPropagation()}
          >
            Open {symbol} →
          </Link>
        </div>
      ) : null}
    </div>
  );
}
