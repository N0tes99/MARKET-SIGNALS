"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";

import { fetchCandles } from "@/services/api";
import { cn } from "@/lib/utils";

interface TickerMiniChartProps {
  symbol: string;
  className?: string;
}

export function TickerMiniChart({ symbol, className }: TickerMiniChartProps) {
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
    queryFn: () => fetchCandles(symbol, "15m", 48),
    enabled: open,
    staleTime: 60_000,
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
    <div ref={rootRef} className={cn("relative inline-flex", className)}>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="font-mono text-lg tracking-wide text-foreground underline-offset-4 transition-colors hover:underline"
        aria-expanded={open}
        aria-label={`${symbol} 15 minute chart`}
        title="15m chart"
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

          <div className="mt-2 h-[88px] w-full">
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
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                  <YAxis domain={["dataMin", "dataMax"]} hide />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(12,14,18,0.95)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      fontSize: 11,
                      fontFamily: "ui-monospace, monospace",
                    }}
                    labelFormatter={() => ""}
                    formatter={(value: number) => [
                      value.toLocaleString(undefined, { maximumFractionDigits: 6 }),
                      "Close",
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="close"
                    stroke={stroke}
                    fill={fill}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
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
