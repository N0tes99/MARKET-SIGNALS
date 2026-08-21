"use client";

import Link from "next/link";

import { useCortexMemory, useExpansionFeed } from "@/hooks/use-expansion";
import { cn } from "@/lib/utils";
import type { ExpansionCandidate, ExpansionState } from "@/services/api";

function stateTone(state: ExpansionState | string): string {
  switch (state) {
    case "primed":
      return "text-amber-200/80";
    case "triggering":
      return "text-orange-300/85";
    case "expanding":
      return "text-bullish";
    default:
      return "text-muted-foreground";
  }
}

function featured(feed: {
  primed: ExpansionCandidate[];
  triggering: ExpansionCandidate[];
  expanding: ExpansionCandidate[];
}): ExpansionCandidate[] {
  const picked: ExpansionCandidate[] = [];
  const seen = new Set<string>();
  for (const c of [...feed.triggering, ...feed.expanding, ...feed.primed]) {
    if (picked.length >= 6) break;
    if (seen.has(c.symbol)) continue;
    seen.add(c.symbol);
    picked.push(c);
  }
  return picked;
}

export function ExpansionPreviewStrip() {
  const feedQuery = useExpansionFeed();
  const cortexQuery = useCortexMemory();
  const primed = feedQuery.data?.primed ?? [];
  const triggering = feedQuery.data?.triggering ?? [];
  const expanding = feedQuery.data?.expanding ?? [];
  const rows = featured({ primed, triggering, expanding });
  const isLoading = feedQuery.isLoading;
  const isError = feedQuery.isError;
  const digest = cortexQuery.data?.digest;

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">
            <Link href="/expansion" className="underline-offset-2 hover:underline">
              Expansion
            </Link>
          </h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            cortex blackboard · paper opens on trigger/expansion only
          </p>
        </div>
        <div className="flex flex-wrap gap-x-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          <span className="text-amber-200/70">primed {primed.length}</span>
          <span className="text-orange-300/80">trigger {triggering.length}</span>
          <span className="text-bullish/70">expand {expanding.length}</span>
          {feedQuery.isFetching && !isLoading ? <span>refreshing</span> : null}
        </div>
      </div>

      {digest ? (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground/45">{digest}</p>
      ) : null}

      {isLoading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="surface skeleton h-24" />
          <div className="surface skeleton h-24" />
          <div className="surface skeleton h-24 hidden lg:block" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4 flex flex-col items-start gap-2">
          <p className="text-sm text-muted-foreground/60">Expansion feed unavailable</p>
          <button
            type="button"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void feedQuery.refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <p className="mt-4 font-mono text-[11px] text-muted-foreground/50">
          No primed / trigger / expansion alerts this tick. Sitting out is valid.
        </p>
      ) : null}

      {rows.length > 0 ? (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((row) => (
            <li key={row.id}>
              <Link
                href={`/assets/${row.symbol}`}
                className="surface-dense-interactive block p-4"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-sm tracking-wide">{row.symbol}</span>
                  <span className={cn("font-mono text-[10px] uppercase tracking-widest", stateTone(row.state))}>
                    {row.state}
                  </span>
                </div>
                <p className="mt-2 font-mono text-[11px] text-muted-foreground/70">
                  net {row.net_score.toFixed(0)} · {row.direction_bias} · compress{" "}
                  {row.compression.score.toFixed(0)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
