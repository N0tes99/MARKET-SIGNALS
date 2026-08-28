"use client";

import Link from "next/link";

import { useRunnerLists } from "@/hooks/use-runners";
import { dimDisplay, formatRelVol, formatTapePct } from "@/lib/runner-display";
import type { RunnerCandidate, RunnerWatchlist } from "@/services/api";

function pickFeatured(lists: {
  early: RunnerCandidate[];
  ignition: RunnerCandidate[];
  running: RunnerCandidate[];
}): RunnerCandidate[] {
  const picked: RunnerCandidate[] = [];
  const seen = new Set<string>();
  for (const c of [...lists.ignition, ...lists.running, ...lists.early]) {
    if (picked.length >= 6) break;
    if (seen.has(c.symbol)) continue;
    seen.add(c.symbol);
    picked.push(c);
  }
  return picked;
}

function listTone(watchlist: RunnerWatchlist): string {
  if (watchlist === "ignition") return "text-amber-200/80";
  if (watchlist === "running") return "text-bullish";
  return "text-muted-foreground";
}

export function RadarPreviewStrip() {
  const { data, isLoading, isError, refetch, isFetching } = useRunnerLists();
  const early = data?.early ?? [];
  const ignition = data?.ignition ?? [];
  const running = data?.running ?? [];
  const featured = pickFeatured({ early, ignition, running });

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
            yahoo tape + fundamentals + sec 8-k · discovery vs valuation · lists can fill ·
            preview — not orders · missing fields stay —
          </p>
        </div>
        <div className="flex flex-wrap gap-x-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          <span>
            yahoo {data?.fundamentals_filled ?? 0}/{data?.symbols_scanned ?? 0}
          </span>
          <span>early {early.length}</span>
          <span className="text-amber-200/70">ignition {ignition.length}</span>
          <span className="text-bullish/70">running {running.length}</span>
          {isFetching && !isLoading ? <span>refreshing</span> : null}
        </div>
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

      {!isLoading && !isError && featured.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground/60">
          No names on early, ignition, or running lists today.
        </p>
      ) : null}

      {!isLoading && featured.length > 0 ? (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((c) => (
            <li key={c.id}>
              <Link href={`/radar/${c.symbol}`} className="surface block p-4 transition-colors hover:bg-white/[0.03]">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-sm tracking-wide">{c.symbol}</span>
                  <span
                    className={`font-mono text-[10px] uppercase tracking-widest ${listTone(c.watchlist)}`}
                  >
                    {c.watchlist === "none" ? c.stage.replaceAll("_", " ") : c.watchlist}
                  </span>
                </div>
                <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                  opp {c.scores.runner_score.toFixed(0)} · risk {c.scores.risk_score.toFixed(0)} ·
                  struct {dimDisplay(c, "structure")} · 20d {formatTapePct(c.ret_20d_pct)} · vol{" "}
                  {formatRelVol(c.relative_volume)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
