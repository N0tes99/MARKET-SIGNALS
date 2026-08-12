"use client";

import Link from "next/link";

import { useRunnerLists } from "@/hooks/use-runners";
import { dimDisplay, formatRelVol, formatTapePct } from "@/lib/runner-display";

/** Compact home strip — same preview label as /radar. */
export function RadarPreviewStrip() {
  const { data, isLoading, isError, refetch, isFetching } = useRunnerLists();
  const early = data?.early ?? [];

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">
            <Link href="/radar" className="underline-offset-2 hover:underline">
              10X Radar
            </Link>
          </h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            preview · structure only · fundamentals not scored
          </p>
        </div>
        {isFetching && !isLoading ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
            refreshing
          </p>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="surface skeleton h-28" />
          <div className="surface skeleton h-28" />
          <div className="surface skeleton h-28 hidden lg:block" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4 flex flex-col items-start gap-2">
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
        <p className="mt-4 text-sm text-muted-foreground/60">
          No names in early accumulation on tape today.
        </p>
      ) : null}

      {!isLoading && early.length > 0 ? (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {early.slice(0, 6).map((c) => (
            <li key={c.id}>
              <Link href={`/radar/${c.symbol}`} className="surface block p-4 transition-colors hover:bg-white/[0.03]">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-sm tracking-wide">{c.symbol}</span>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    {c.stage.replaceAll("_", " ")}
                  </span>
                </div>
                <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                  struct {dimDisplay(c, "structure")} · 20d {formatTapePct(c.ret_20d_pct)} ·
                  vol {formatRelVol(c.relative_volume)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
