"use client";

import Link from "next/link";
import { useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { useCryptoRadar, useRunnersFeed } from "@/hooks/use-runners";
import { dimDisplay, formatRelVol, formatTapePct } from "@/lib/runner-display";
import type {
  CryptoRadarBucket,
  CryptoRadarCandidate,
  RunnerCandidate,
  RunnerWatchlist,
} from "@/services/api";

type RadarTrack = "equities" | "crypto";

const EQUITY_BUCKETS: {
  key: Exclude<RunnerWatchlist, "none">;
  label: string;
  hint: string;
}[] = [
  { key: "early", label: "Early", hint: "inflection / accumulation" },
  { key: "ignition", label: "Ignition", hint: "structure + catalyst or fund" },
  { key: "running", label: "Running", hint: "discovery / momentum" },
];

const CRYPTO_BUCKETS: {
  key: Exclude<CryptoRadarBucket, "none">;
  label: string;
  hint: string;
}[] = [
  { key: "watch", label: "Watch", hint: "soft momentum or funding build" },
  { key: "crowded", label: "Crowded", hint: "extreme funding / OI squeeze setup" },
  { key: "running", label: "Running", hint: "strong multi-horizon momentum" },
];

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatBps(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)} bps`;
}

function EquityBucketColumn({
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

function CryptoBucketColumn({
  label,
  hint,
  names,
}: {
  label: string;
  hint: string;
  names: CryptoRadarCandidate[];
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
                href={`/assets/${c.symbol}`}
                className="surface block p-3 transition-colors hover:bg-white/[0.03]"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-sm tracking-wide">{c.symbol}</span>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    score {c.score.toFixed(0)}
                  </span>
                </div>
                <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">
                  12h {formatPct(c.mom_12h_pct)} · 20d {formatPct(c.mom_20d_pct)} · fund{" "}
                  {formatBps(c.funding_bps)}
                  {c.basis_pct != null ? ` · basis ${formatPct(c.basis_pct)}` : ""}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const TRACK_LABELS: Record<RadarTrack, string> = {
  equities: "Equities",
  crypto: "Crypto",
};

function TrackToggle({
  track,
  onChange,
}: {
  track: RadarTrack;
  onChange: (next: RadarTrack) => void;
}) {
  return (
    <div className="inline-flex border border-white/[0.08]">
      {(["equities", "crypto"] as const).map((key) => {
        const active = track === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors ${
              active
                ? "bg-white/[0.08] text-foreground"
                : "text-muted-foreground/60 hover:text-muted-foreground"
            }`}
          >
            {TRACK_LABELS[key]}
          </button>
        );
      })}
    </div>
  );
}

function EquitiesTrack() {
  const { data, isLoading, isError, refetch, isFetching } = useRunnersFeed();
  const candidates = data?.candidates ?? [];
  const listed = candidates.filter((c) => c.watchlist !== "none");

  return (
    <>
      <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
        Yahoo tape + fundamentals. Missing fields stay as em dash — no fake 50s. Seed names are a
        benchmark set, not recommendations.
      </p>

      <div className="mt-4 flex flex-wrap items-baseline gap-4">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          yahoo {data?.fundamentals_filled ?? 0}/{data?.symbols_scanned ?? 0} · early{" "}
          {candidates.filter((c) => c.watchlist === "early").length} · ignition{" "}
          {candidates.filter((c) => c.watchlist === "ignition").length} · running{" "}
          {candidates.filter((c) => c.watchlist === "running").length}
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
          {EQUITY_BUCKETS.map((bucket) => (
            <EquityBucketColumn
              key={bucket.key}
              label={bucket.label}
              hint={bucket.hint}
              names={candidates.filter((c) => c.watchlist === bucket.key)}
            />
          ))}
        </div>
      ) : null}

      {!isLoading && !isError && candidates.length > 0 ? (
        <div className="mt-10 hidden overflow-x-auto md:block">
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
                  <td className="py-2.5 pr-3 font-mono text-xs">{dimDisplay(c, "structure")}</td>
                  <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                    {c.rs_benchmark ?? "—"} {formatTapePct(c.rs_pct)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-xs">
                    {formatRelVol(c.relative_volume)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{formatTapePct(c.ret_20d_pct)}</td>
                  <td className="py-2.5 pr-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    {c.stage.replaceAll("_", " ")}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-xs">
                    {c.scores.runner_score.toFixed(0)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{c.scores.risk_score.toFixed(0)}</td>
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
    </>
  );
}

function CryptoTrack() {
  const { data, isLoading, isError, refetch, isFetching } = useCryptoRadar();
  const candidates = data?.candidates ?? [];
  const listed = candidates.filter((c) => c.bucket !== "none");

  return (
    <>
      <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
        Possible crypto perp moves on the perp-v2 universe (16 names). Momentum from spot tape;
        funding + basis from Bybit when reachable, else OKX. Learned coefficients from paper —
        not an AI-trained model, and not live orders.
      </p>

      <div className="mt-4 flex flex-wrap items-baseline gap-4">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          funding {data?.funding_filled ?? 0}/{data?.symbols_scanned ?? 0} · watch{" "}
          {data?.watch.length ?? 0} · crowded {data?.crowded.length ?? 0} · running{" "}
          {data?.running.length ?? 0}
        </p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          {(data?.perp_momentum_n ?? 0) > 0
            ? `perp momentum ${data?.perp_momentum_n} paper · ${data?.perp_momentum_win_rate ?? 0}% win · coeffs ${data?.coefficients_preset ?? "default"}`
            : "learning from paper"}
        </p>
        {isFetching && !isLoading ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
            refreshing
          </p>
        ) : null}
        <Link
          href="/perps"
          className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
        >
          Open perps board
        </Link>
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
          <p className="text-sm text-muted-foreground/60">Crypto radar unavailable</p>
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
          No names on watch, crowded, or running lists today.
        </p>
      ) : null}

      {!isLoading && !isError && listed.length > 0 ? (
        <div className="mt-6 grid gap-8 md:grid-cols-3">
          {CRYPTO_BUCKETS.map((bucket) => (
            <CryptoBucketColumn
              key={bucket.key}
              label={bucket.label}
              hint={bucket.hint}
              names={(data?.[bucket.key] ?? []).filter((c) => c.bucket === bucket.key)}
            />
          ))}
        </div>
      ) : null}

      {!isLoading && !isError && candidates.length > 0 ? (
        <div className="mt-10 hidden overflow-x-auto md:block">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead>
              <tr className="label-caps border-b border-white/[0.06] text-muted-foreground/70">
                <th className="py-2 pr-3 font-normal">Symbol</th>
                <th className="py-2 pr-3 font-normal">Bucket</th>
                <th className="py-2 pr-3 font-normal">Score</th>
                <th className="py-2 pr-3 font-normal">12h</th>
                <th className="py-2 pr-3 font-normal">20d</th>
                <th className="py-2 pr-3 font-normal">Funding</th>
                <th className="py-2 pr-3 font-normal">OI Δ</th>
                <th className="py-2 font-normal">Source</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id} className="border-b border-white/[0.04]">
                  <td className="py-2.5 pr-3">
                    <Link
                      href={`/assets/${c.symbol}`}
                      className="font-mono tracking-wide underline-offset-2 hover:underline"
                    >
                      {c.symbol}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    {c.bucket === "none" ? "—" : c.bucket}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{c.score.toFixed(0)}</td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{formatPct(c.mom_12h_pct)}</td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{formatPct(c.mom_20d_pct)}</td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{formatBps(c.funding_bps)}</td>
                  <td className="py-2.5 pr-3 font-mono text-xs">{formatPct(c.oi_change_pct)}</td>
                  <td className="py-2.5 font-mono text-xs text-muted-foreground">
                    {c.funding_source || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}

export default function RadarPage() {
  const [track, setTrack] = useState<RadarTrack>("equities");

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="10X Radar" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <div className="mb-6">
          <TrackToggle track={track} onChange={setTrack} />
        </div>
        {track === "equities" ? <EquitiesTrack /> : <CryptoTrack />}
      </div>
    </main>
  );
}
