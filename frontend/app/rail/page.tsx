"use client";

import { useState } from "react";

import { useRailDesk, useSimulateRailEnvelope } from "@/hooks/use-rail-desk";
import { cn } from "@/lib/utils";
import type { RailEnvelope, RailFill, RailVenue } from "@/services/api";

function edgeTone(n: number): string {
  if (n >= 75) return "text-emerald-300/85";
  if (n >= 60) return "text-cyan-200/80";
  return "text-muted-foreground/70";
}

function VenueCard({ venue }: { venue: RailVenue }) {
  return (
    <article className="surface p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-mono text-sm text-foreground/90">{venue.label}</h3>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          {venue.status}
        </span>
      </div>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
        {venue.chain} · {venue.market_kind}
      </p>
      <p className="mt-3 text-sm text-muted-foreground/80">{venue.role}</p>
      <p className="mt-2 font-mono text-[10px] leading-relaxed text-muted-foreground/50">
        {venue.note}
      </p>
    </article>
  );
}

function EnvelopeCard({
  envelope,
  onSimulate,
  pending,
}: {
  envelope: RailEnvelope;
  onSimulate: (id: string) => void;
  pending: boolean;
}) {
  const open = envelope.status === "open";
  return (
    <article className="surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground/50">
          {envelope.market_kind} · {envelope.side} · band {envelope.size_band}
        </p>
        <span className={cn("font-mono text-sm", edgeTone(envelope.edge_score))}>
          edge {envelope.edge_score.toFixed(0)}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Urgency</dt>
          <dd className="font-mono">{envelope.urgency}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">TTL</dt>
          <dd className="font-mono">{envelope.ttl_seconds}s</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Invalidation</dt>
          <dd className="font-mono">{envelope.invalidation}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Rails to</dt>
          <dd className="font-mono">{envelope.target_venue}</dd>
        </div>
      </dl>
      <p className="mt-3 truncate font-mono text-[10px] text-muted-foreground/40">
        handle {envelope.instrument_handle}
      </p>
      {open ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => onSimulate(envelope.envelope_id)}
          className="mt-4 font-mono text-[10px] uppercase tracking-widest text-cyan-100/80 underline-offset-4 hover:underline disabled:opacity-40"
        >
          {pending ? "Acking…" : "Dry-run paper ack"}
        </button>
      ) : (
        <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
          closed · clerk sits out
        </p>
      )}
    </article>
  );
}

function FillRow({ fill }: { fill: RailFill }) {
  return (
    <li className="border-t border-white/[0.05] py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-[11px] text-foreground/80">
          {fill.status} · {fill.venue} · {fill.side} · {fill.size_band}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground/45">
          {fill.latency_ms}ms
        </span>
      </div>
      <p className="mt-1 font-mono text-[10px] leading-relaxed text-muted-foreground/50">
        {fill.reason}
      </p>
    </li>
  );
}

export default function RailPage() {
  const deskQuery = useRailDesk();
  const simulate = useSimulateRailEnvelope();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const desk = deskQuery.data;
  const envelopes = desk?.envelopes ?? [];
  const openEnvelopes = envelopes.filter((row) => row.status === "open");
  const closedEnvelopes = envelopes.filter((row) => row.status === "closed");

  return (
    <main className="container mx-auto max-w-6xl space-y-8 px-4 py-8">
      <div>
        <p className="label-caps text-cyan-200/60">Nested clerk</p>
        <h1 className="mt-2 font-brand text-3xl font-medium tracking-tight">
          Opportunity in. Thesis out.
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Rail does not see the trade. It sees side, size band, urgency, and edge — then
          executes like a human order clerk, faster. Phase B reads Hyperliquid books,
          HL funding, and HIP-4 outcomes — things the desk does not scan. Paper dry-run
          only. Live adapters cannot place orders. No trade is a valid decision.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="surface p-4">
          <p className="label-caps">Kill switch</p>
          <p className="mt-2 font-mono text-sm">
            {desk?.armed ? "armed" : "safe"} · live {desk?.live_enabled ? "on" : "off"}
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
            {desk
              ? `phase ${desk.phase} · venue ${desk.default_venue}`
              : "waiting for clerk snapshot"}
          </p>
        </div>
        <div className="surface p-4">
          <p className="label-caps">Clerk book</p>
          <p className="mt-2 font-mono text-sm">
            {openEnvelopes.length} open · {closedEnvelopes.length} closed
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
            {desk?.sitting_out ? "sitting out" : "opportunities queued"}
          </p>
        </div>
        <div className="surface p-4">
          <p className="label-caps">Dry-run fills</p>
          <p className="mt-2 font-mono text-sm">{desk?.fills.length ?? 0} acks</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
            not live exchange orders
          </p>
        </div>
      </div>

      <section>
        <h2 className="label-caps">Venues</h2>
        <p className="mt-1 mb-4 text-sm text-muted-foreground">
          Hyperliquid is the rail: identify on its books, fill there later. Drift is the
          Solana option. Polymarket waits unless HIP-4 does not list the event.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          {(desk?.venues ?? []).map((venue) => (
            <VenueCard key={venue.id} venue={venue} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="label-caps">Open opportunities</h2>
        <p className="mt-1 mb-4 text-sm text-muted-foreground">
          Handles are HMAC stubs. The clerk cannot reverse them into a ticker.
          These ideas come from Hyperliquid, not the desk grade.
        </p>
        {deskQuery.isLoading ? (
          <p className="font-mono text-[11px] text-muted-foreground/60">Loading clerk book…</p>
        ) : null}
        {deskQuery.isError ? (
          <p className="font-mono text-[11px] text-rose-300/80">Clerk snapshot failed.</p>
        ) : null}
        {desk && openEnvelopes.length === 0 ? (
          <p className="font-mono text-sm text-muted-foreground/70">
            Sitting out. Empty is healthy.
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {openEnvelopes.map((envelope) => (
              <EnvelopeCard
                key={envelope.envelope_id}
                envelope={envelope}
                pending={simulate.isPending && pendingId === envelope.envelope_id}
                onSimulate={(id) => {
                  setPendingId(id);
                  simulate.mutate(id, { onSettled: () => setPendingId(null) });
                }}
              />
            ))}
          </div>
        )}
      </section>

      {closedEnvelopes.length > 0 ? (
        <section>
          <h2 className="label-caps">Recently managed</h2>
          <ul className="mt-3 surface px-4 py-2">
            {closedEnvelopes.slice(0, 8).map((envelope) => (
              <li
                key={envelope.envelope_id}
                className="border-t border-white/[0.05] py-2 first:border-t-0 first:pt-0"
              >
                <span className="font-mono text-[11px] text-muted-foreground/70">
                  {envelope.market_kind} {envelope.side} · {envelope.size_band} · edge{" "}
                  {envelope.edge_score.toFixed(0)} · {envelope.target_venue}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h2 className="label-caps">Clerk tape</h2>
        {(desk?.fills.length ?? 0) === 0 ? (
          <p className="mt-3 font-mono text-[11px] text-muted-foreground/55">
            No dry-run acks yet.
          </p>
        ) : (
          <ul className="mt-3 surface px-4 py-2">
            {(desk?.fills ?? [])
              .slice()
              .reverse()
              .map((fill) => (
                <FillRow key={fill.fill_id} fill={fill} />
              ))}
          </ul>
        )}
      </section>
    </main>
  );
}
