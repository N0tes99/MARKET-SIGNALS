"use client";

import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { useRunnersFeed } from "@/hooks/use-runners";
import { dimDisplay, formatRelVol, formatTapePct } from "@/lib/runner-display";

export default function RadarPage() {
  const { data, isLoading, isError, refetch, isFetching } = useRunnersFeed();
  const candidates = data?.candidates ?? [];
  const early = candidates.filter((c) => c.watchlist === "early");

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="10X Radar" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Yahoo tape + fundamentals. Missing fields stay as em dash — no fake
          50s. Seed names are a benchmark set, not recommendations.
        </p>

        <div className="mt-4 flex flex-wrap items-baseline gap-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            phase {data?.candidates[0]?.phase ?? "3_yahoo"} · scanned{" "}
            {data?.symbols_scanned ?? 0}
          </p>
          {isFetching && !isLoading ? (
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
              refreshing
            </p>
          ) : null}
        </div>

        {isLoading ? (
          <div className="mt-6 space-y-2">
            <div className="surface skeleton h-10" />
            <div className="surface skeleton h-10" />
            <div className="surface skeleton h-10" />
          </div>
        ) : null}

        {isError ? (
          <div className="mt-6 flex flex-col items-start gap-2">
            <p className="text-sm text-muted-foreground/60">Radar feed unavailable</p>
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {!isLoading && !isError && early.length === 0 ? (
          <p className="mt-6 text-sm text-muted-foreground/60">
            No names in early accumulation on tape today.
          </p>
        ) : null}

        {!isLoading && !isError && candidates.length > 0 ? (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead>
                <tr className="label-caps border-b border-white/[0.06] text-muted-foreground/70">
                  <th className="py-2 pr-3 font-normal">Symbol</th>
                  <th className="py-2 pr-3 font-normal">Struct</th>
                  <th className="py-2 pr-3 font-normal">RS</th>
                  <th className="py-2 pr-3 font-normal">Rel vol</th>
                  <th className="py-2 pr-3 font-normal">20d</th>
                  <th className="py-2 pr-3 font-normal">Stage</th>
                  <th className="py-2 pr-3 font-normal">Runner</th>
                  <th className="py-2 pr-3 font-normal">Risk</th>
                  <th className="py-2 pr-3 font-normal">Fund</th>
                  <th className="py-2 pr-3 font-normal">Cat</th>
                  <th className="py-2 font-normal">Disc</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.id} className="border-b border-white/[0.04]">
                    <td className="py-2.5 pr-3">
                      <Link
                        href={`/radar/${c.symbol}`}
                        className="font-mono tracking-wide underline-offset-2 hover:underline"
                      >
                        {c.symbol}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs">
                      {dimDisplay(c, "structure")}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                      {c.rs_benchmark ?? "—"} {formatTapePct(c.rs_pct)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs">
                      {formatRelVol(c.relative_volume)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs">
                      {formatTapePct(c.ret_20d_pct)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      {c.stage.replaceAll("_", " ")}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs">
                      {c.scores.runner_score.toFixed(0)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs">
                      {c.scores.risk_score.toFixed(0)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                      {dimDisplay(c, "fundamental")}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                      {dimDisplay(c, "catalyst")}
                    </td>
                    <td className="py-2.5 font-mono text-xs text-muted-foreground">
                      {dimDisplay(c, "discovery_gap")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </main>
  );
}
