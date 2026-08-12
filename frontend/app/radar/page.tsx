"use client";

import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { useRunnersFeed } from "@/hooks/use-runners";
import { dimDisplay, formatRelVol, formatTapePct } from "@/lib/runner-display";
import type { RunnerCandidate, RunnerWatchlist } from "@/services/api";

const BUCKETS: { key: Exclude<RunnerWatchlist, "none">; label: string; hint: string }[] = [
  { key: "early", label: "Early", hint: "inflection / accumulation" },
  { key: "ignition", label: "Ignition", hint: "structure + catalyst or fund" },
  { key: "running", label: "Running", hint: "discovery / momentum" },
];

function BucketColumn({
  label,
  hint,
  names,
}: {
  label: string;
  hint: string;
  names: RunnerCandidate[];
}) {
  return (
    <section>
      <h2 className="label-caps">
        {label} · {names.length}
      </h2>
      <p className="mt-1 mb-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
        {hint}
      </p>
      {names.length === 0 ? (
        <p className="text-sm text-muted-foreground/50">Empty today.</p>
      ) : (
        <ul className="grid gap-2">
          {names.map((c) => (
            <li key={c.id}>
              <Link
                href={`/radar/${c.symbol}`}
                className="surface block p-3 transition-colors hover:bg-white/[0.03]"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-sm tracking-wide">{c.symbol}</span>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    {c.stage.replaceAll("_", " ")}
                  </span>
                </div>
                <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">
                  runner {c.scores.runner_score.toFixed(0)} · struct {dimDisplay(c, "structure")} ·
                  fund {dimDisplay(c, "fundamental")}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function RadarPage() {
  const { data, isLoading, isError, refetch, isFetching } = useRunnersFeed();
  const candidates = data?.candidates ?? [];
  const listed = candidates.filter((c) => c.watchlist !== "none");

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="10X Radar" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Yahoo tape + fundamentals. Missing fields stay as em dash — no fake
          50s. Seed names are a benchmark set, not recommendations. Ignition and
          running lists can fill now that Yahoo scores the missing dims.
        </p>

        <div className="mt-4 flex flex-wrap items-baseline gap-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            yahoo {data?.fundamentals_filled ?? 0}/{data?.symbols_scanned ?? 0} ·
            early {candidates.filter((c) => c.watchlist === "early").length} ·
            ignition {candidates.filter((c) => c.watchlist === "ignition").length}{" "}
            · running {candidates.filter((c) => c.watchlist === "running").length}
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

        {!isLoading && !isError && listed.length === 0 ? (
          <p className="mt-6 text-sm text-muted-foreground/60">
            No names on early, ignition, or running lists today.
          </p>
        ) : null}

        {!isLoading && !isError && listed.length > 0 ? (
          <div className="mt-6 grid gap-8 md:grid-cols-3">
            {BUCKETS.map((bucket) => (
              <BucketColumn
                key={bucket.key}
                label={bucket.label}
                hint={bucket.hint}
                names={candidates.filter((c) => c.watchlist === bucket.key)}
              />
            ))}
          </div>
        ) : null}

        {!isLoading && !isError && candidates.length > 0 ? (
          <div className="mt-10 overflow-x-auto">
            <table className="w-full min-w-[56rem] text-left text-sm">
              <thead>
                <tr className="label-caps border-b border-white/[0.06] text-muted-foreground/70">
                  <th className="py-2 pr-3 font-normal">Symbol</th>
                  <th className="py-2 pr-3 font-normal">List</th>
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
                    <td className="py-2.5 pr-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      {c.watchlist === "none" ? "—" : c.watchlist}
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
