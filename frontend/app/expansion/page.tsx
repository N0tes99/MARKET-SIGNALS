"use client";

import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { useCortexMemory, useExpansionFeed } from "@/hooks/use-expansion";
import { cn } from "@/lib/utils";
import type { ExpansionCandidate, ExpansionState } from "@/services/api";

function stateClass(state: ExpansionState | string): string {
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

function CandidateCard({ row }: { row: ExpansionCandidate }) {
  return (
    <article className="surface p-4">
      <div className="flex items-baseline justify-between gap-2">
        <Link
          href={`/assets/${row.symbol}`}
          className="font-mono text-sm tracking-wide underline-offset-2 hover:underline"
        >
          {row.symbol}
        </Link>
        <span className={cn("font-mono text-[10px] uppercase tracking-widest", stateClass(row.state))}>
          {row.state}
        </span>
      </div>
      <dl className="mt-3 space-y-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Compression</dt>
          <dd className="font-mono">{row.compression.score.toFixed(0)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Squeeze fuel</dt>
          <dd className="font-mono">{row.squeeze.score.toFixed(0)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Net score</dt>
          <dd className="font-mono">{row.net_score.toFixed(0)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Trigger</dt>
          <dd className="font-mono">{row.trigger_active ? "active" : "off"}</dd>
        </div>
      </dl>
      <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
        {row.direction_bias} · {row.horizon}
      </p>
    </article>
  );
}

export default function ExpansionPage() {
  const feedQuery = useExpansionFeed();
  const cortexQuery = useCortexMemory();
  const candidates = feedQuery.data?.candidates ?? [];
  const primed = feedQuery.data?.primed ?? [];
  const triggering = feedQuery.data?.triggering ?? [];
  const expanding = feedQuery.data?.expanding ?? [];

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Expansion" />
      <div className="container mx-auto max-w-6xl space-y-6 px-4 py-8">
        <div>
          <p className="label-caps">Surface 5</p>
          <h1 className="mt-2 font-brand text-3xl font-medium tracking-tight">Expansion radar</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Compression, squeeze fuel, breakout trigger. Cortex specialists (regime +
            derivatives) annotate the blackboard. Does not fold into 13-category grades.
            Paper opens on TRIGGER/EXPANSION only — PRIMED is watch. Sitting out is valid.
          </p>
        </div>

        <section className="surface p-4 sm:p-5">
          <p className="label-caps">Cortex</p>
          {cortexQuery.isLoading ? (
            <p className="mt-2 font-mono text-[11px] text-muted-foreground/50">Loading working memory…</p>
          ) : null}
          {cortexQuery.isError ? (
            <p className="mt-2 text-sm text-muted-foreground/60">Cortex unavailable</p>
          ) : null}
          {cortexQuery.data ? (
            <>
              <p className="mt-2 font-mono text-[11px] text-muted-foreground/75">
                {cortexQuery.data.digest || `tick ${cortexQuery.data.tick_id}`}
              </p>
              <p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
                primed {cortexQuery.data.primed.length || "none"}
                {" · "}
                trigger/expand {cortexQuery.data.triggering.length || "none"}
                {" · "}
                universe {cortexQuery.data.universe.length}
              </p>
              {cortexQuery.data.notes.length > 0 ? (
                <ul className="mt-3 space-y-1 font-mono text-[11px] text-muted-foreground/65">
                  {cortexQuery.data.notes.slice(0, 6).map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
        </section>

        {feedQuery.isLoading ? (
          <p className="font-mono text-[11px] text-muted-foreground/50">Loading expansion scan…</p>
        ) : null}

        {feedQuery.isError ? (
          <div>
            <p className="text-sm text-muted-foreground/60">Expansion feed unavailable</p>
            <button
              type="button"
              className="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void feedQuery.refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {!feedQuery.isLoading && !feedQuery.isError ? (
          <>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
              primed {primed.length} · triggering {triggering.length} · expanding {expanding.length}{" "}
              · scanned {feedQuery.data?.symbols_scanned ?? candidates.length}
            </p>
            <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {candidates.map((row) => (
                <CandidateCard key={row.id} row={row} />
              ))}
            </div>
            {candidates.length === 0 ? (
              <p className="font-mono text-[11px] text-muted-foreground/50">
                No expansion readings this scan.
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
