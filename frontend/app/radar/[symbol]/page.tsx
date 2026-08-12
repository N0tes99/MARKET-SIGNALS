"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { useRunnerDetail } from "@/hooks/use-runners";
import { dimDisplay, formatRelVol, formatTapePct } from "@/lib/runner-display";

export default function RadarDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = String(params?.symbol ?? "").toUpperCase();
  const { data, isLoading, isError, refetch } = useRunnerDetail(symbol);
  const c = data?.candidate;

  return (
    <main className="min-h-screen">
      <SiteHeader compact title={symbol || "Radar"} />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <Link
          href="/radar"
          className="label-caps inline-flex text-muted-foreground/80 transition-colors hover:text-foreground"
        >
          ← radar
        </Link>

        <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          preview · structure only · fundamentals not scored
        </p>

        {isLoading ? <div className="surface skeleton mt-6 h-40" /> : null}

        {isError ? (
          <div className="mt-6 flex flex-col items-start gap-2">
            <p className="text-sm text-muted-foreground/60">Unable to load {symbol}.</p>
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {c ? (
          <div className="mt-6 space-y-6">
            <div className="surface p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h1 className="font-mono text-xl tracking-wide">{c.symbol}</h1>
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {c.stage.replaceAll("_", " ")} · {c.watchlist}
                </span>
              </div>
              <p className="mt-3 font-mono text-xs text-muted-foreground">
                runner {c.scores.runner_score.toFixed(0)} (capped) · risk{" "}
                {c.scores.risk_score.toFixed(0)} · conf {c.confidence.toFixed(0)} ·{" "}
                {c.phase}
              </p>
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                struct {dimDisplay(c, "structure")} · 20d {formatTapePct(c.ret_20d_pct)} ·
                vol {formatRelVol(c.relative_volume)} · rs {c.rs_benchmark ?? "—"}{" "}
                {formatTapePct(c.rs_pct)}
              </p>
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                fund {dimDisplay(c, "fundamental")} · cat {dimDisplay(c, "catalyst")} ·
                disc {dimDisplay(c, "discovery_gap")}
              </p>
            </div>

            {c.factors.length > 0 ? (
              <div className="surface p-5">
                <h2 className="label-caps">Factors</h2>
                <ul className="mt-3 space-y-1.5">
                  {c.factors.map((f) => (
                    <li key={f} className="font-mono text-xs text-muted-foreground">
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {c.conflicts.length > 0 ? (
              <div className="surface p-5">
                <h2 className="label-caps">Conflicts</h2>
                <ul className="mt-3 space-y-1.5">
                  {c.conflicts.map((f) => (
                    <li key={f} className="text-xs text-neutral">
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {c.risk_flags.length > 0 ? (
              <div className="surface p-5">
                <h2 className="label-caps">Risk flags</h2>
                <ul className="mt-3 space-y-1.5">
                  {c.risk_flags.map((f) => (
                    <li key={f} className="font-mono text-xs text-muted-foreground">
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </main>
  );
}
