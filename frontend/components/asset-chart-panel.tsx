"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CandlestickChart } from "@/components/candlestick-chart";
import { MiniSparkline } from "@/components/mini-sparkline";
import { cn } from "@/lib/utils";
import { fetchCandles } from "@/services/api";

type ChartMode = "candle" | "line";
type ChartTf = "1m" | "5m" | "15m";

const TIMEFRAMES: { id: ChartTf; bars: number; refetchMs: number }[] = [
  { id: "1m", bars: 120, refetchMs: 20_000 },
  { id: "5m", bars: 96, refetchMs: 45_000 },
  { id: "15m", bars: 96, refetchMs: 60_000 },
];

export function AssetChartPanel({ symbol }: { symbol: string }) {
  const [mode, setMode] = useState<ChartMode>("candle");
  const [tf, setTf] = useState<ChartTf>("15m");
  const spec = TIMEFRAMES.find((t) => t.id === tf) ?? TIMEFRAMES[2];

  const candlesQuery = useQuery({
    queryKey: ["candles", symbol, spec.id, spec.bars],
    queryFn: () => fetchCandles(symbol, spec.id, spec.bars),
    staleTime: Math.min(spec.refetchMs, 30_000),
    refetchInterval: spec.refetchMs,
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
  const lastBar = candles[candles.length - 1]?.t;

  return (
    <section className="surface p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="label-caps">Price</h2>
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {tf} · {candles.length || "—"} bars
            {lastBar
              ? ` · as of ${new Date(lastBar).toLocaleTimeString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                })}`
              : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="seg-control" role="group" aria-label="Chart timeframe">
            {TIMEFRAMES.map((item) => (
              <button
                key={item.id}
                type="button"
                data-active={tf === item.id}
                className="seg-control-btn"
                onClick={() => setTf(item.id)}
              >
                {item.id}
              </button>
            ))}
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
      </div>

      <div className={cn("mt-3 h-[160px] w-full sm:h-[200px]", mode === "candle" && "sm:h-[220px]")}>
        {candlesQuery.isLoading ? (
          <p className="pt-16 text-center font-mono text-[11px] text-muted-foreground">
            Loading {tf} chart…
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
            No {tf} bars yet — market closed or feed delayed. Try 15m.
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
