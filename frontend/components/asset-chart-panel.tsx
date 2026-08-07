"use client";

import { useQuery } from "@tanstack/react-query";

import { MiniSparkline } from "@/components/mini-sparkline";
import { fetchCandles } from "@/services/api";

export function AssetChartPanel({ symbol }: { symbol: string }) {
  const candlesQuery = useQuery({
    queryKey: ["candles", symbol, "15m", "detail"],
    queryFn: () => fetchCandles(symbol, "15m", 48),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
    retry: 1,
    retryDelay: 3_000,
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
    <section className="surface p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="label-caps">Price</h2>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          15m · last {points.length || "—"} bars
        </p>
      </div>
      <div className="mt-3 h-[160px] w-full sm:h-[200px]">
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
        {!candlesQuery.isLoading && !candlesQuery.isError && points.length === 0 ? (
          <p className="pt-16 text-center font-mono text-[11px] text-muted-foreground">
            No bars yet
          </p>
        ) : null}
        {points.length > 0 ? (
          <MiniSparkline points={points} stroke={stroke} fill={fill} />
        ) : null}
      </div>
    </section>
  );
}
