"use client";

import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";

import { fetchCandles } from "@/services/api";

const MiniSparkline = dynamic(
  () => import("@/components/mini-sparkline").then((mod) => mod.MiniSparkline),
  {
    ssr: false,
    loading: () => (
      <p className="pt-16 text-center font-mono text-[11px] text-muted-foreground">Loading chart…</p>
    ),
  },
);

export function AssetChartPanel({ symbol }: { symbol: string }) {
  const candlesQuery = useQuery({
    queryKey: ["candles", symbol, "15m", "detail"],
    queryFn: () => fetchCandles(symbol, "15m", 48),
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
    <section className="surface mt-6 p-4 sm:p-5">
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
          <p className="pt-16 text-center text-sm text-bearish">Chart unavailable</p>
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
