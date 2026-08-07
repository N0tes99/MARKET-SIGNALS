"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CandlestickChart } from "@/components/candlestick-chart";
import { MiniSparkline } from "@/components/mini-sparkline";
import { cn } from "@/lib/utils";
import { fetchCandles } from "@/services/api";

type ChartMode = "candle" | "line";

export function AssetChartPanel({ symbol }: { symbol: string }) {
  const [mode, setMode] = useState<ChartMode>("candle");

  const candlesQuery = useQuery({
    queryKey: ["candles", symbol, "15m", "detail"],
    queryFn: () => fetchCandles(symbol, "15m", 48),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
    retry: 1,
    retryDelay: 3_000,
  });

  const candles = candlesQuery.data?.candles ?? [];
  const points = candles.map((c) => ({ t: c.t, close: c.c }));

  const first = points[0]?.close;
  const last = points[points.length - 1]?.close;
  const up = first != null && last != null ? last >= first : true;
  const stroke = up ? "#8fa88a" : "#a67c7c";
  const fill = up ? "rgba(143,168,138,0.2)" : "rgba(166,124,124,0.2)";

  return (
    <section className="surface p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="label-caps">Price</h2>
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            15m · last {candles.length || "—"} bars
          </p>
        </div>
        <div className="seg-control" role="group" aria-label="Chart style">
          <button
            type="button"
            data-active={mode === "candle"}
            className="seg-control-btn"
            onClick={() => setMode("candle")}
          >
            Candle
          </button>
          <button
            type="button"
            data-active={mode === "line"}
            className="seg-control-btn"
            onClick={() => setMode("line")}
          >
            Line
          </button>
        </div>
      </div>

      <div className={cn("mt-3 h-[160px] w-full sm:h-[200px]", mode === "candle" && "sm:h-[220px]")}>
        {candlesQuery.isLoading ? (
          <p className="pt-16 text-center font-mono text-[11px] text-muted-foreground">
            Loading chart…
          </p>
        ) : null}
        {candlesQuery.isError ? (
          <div className="flex flex-col items-center gap-2 pt-12">
            <p className="text-sm text-bearish">Chart unavailable</p>
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void candlesQuery.refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}
        {!candlesQuery.isLoading && !candlesQuery.isError && candles.length === 0 ? (
          <p className="pt-16 text-center font-mono text-[11px] text-muted-foreground">
            No bars yet
          </p>
        ) : null}
        {candles.length > 0 && mode === "candle" ? (
          <CandlestickChart candles={candles} upColor={stroke} downColor="#a67c7c" />
        ) : null}
        {points.length > 0 && mode === "line" ? (
          <MiniSparkline points={points} stroke={stroke} fill={fill} />
        ) : null}
      </div>
    </section>
  );
}
