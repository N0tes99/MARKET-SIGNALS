"use client";

import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import {
  fetchPublicPreview,
  type AssetSummary,
  type PaperLedger,
} from "@/services/api";

function money(n: number): string {
  const sign = n > 0 ? "+" : n < 0 ? "" : "";
  return `${sign}${n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  })}`;
}

function pct(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function pnlTone(n: number): string {
  if (n > 0) return "text-bullish";
  if (n < 0) return "text-bearish";
  return "text-muted-foreground/70";
}

function confTone(n: number): string {
  if (n >= 65) return "text-bullish";
  if (n <= 40) return "text-bearish";
  return "text-muted-foreground";
}

function MiniLedger({ title, hint, ledger }: { title: string; hint: string; ledger: PaperLedger }) {
  return (
    <div className="border border-white/[0.06] bg-card/10 px-3 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="label-caps text-muted-foreground/70">{title}</p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
          {hint}
        </p>
      </div>
      <p className={cn("mt-2 font-mono text-lg tracking-tight", pnlTone(ledger.total_pnl))}>
        {money(ledger.total_pnl)}
      </p>
      <p className={cn("mt-0.5 font-mono text-[11px]", pnlTone(ledger.total_pnl))}>
        {pct(ledger.return_pct)} · equity {money(ledger.equity)}
      </p>
      <p className="mt-1 font-mono text-[10px] text-muted-foreground/55">
        <span className={pnlTone(ledger.realized_pnl)}>closed {money(ledger.realized_pnl)}</span>
        {" · "}
        <span className={pnlTone(ledger.unrealized_pnl)}>
          open {money(ledger.unrealized_pnl)}
        </span>
        {" · "}
        {ledger.open_positions} pos
      </p>
    </div>
  );
}

function PickRow({ pick }: { pick: AssetSummary }) {
  return (
    <li className="flex items-baseline justify-between gap-3 border-b border-white/[0.05] py-2 last:border-b-0">
      <div className="min-w-0">
        <p className="font-mono text-sm tracking-tight text-foreground">{pick.symbol}</p>
        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          {pick.trade_grade} · {pick.trade_state.toLowerCase()} · {pick.execution_signal}
        </p>
      </div>
      <p className={cn("shrink-0 font-mono text-sm tabular-nums", confTone(pick.confidence))}>
        {pick.confidence.toFixed(0)}%
      </p>
    </li>
  );
}

function PreviewSkeleton() {
  return (
    <div className="surface animate-pulse space-y-4 p-5" aria-hidden>
      <div className="h-3 w-24 bg-white/[0.06]" />
      <div className="h-16 bg-white/[0.04]" />
      <div className="h-16 bg-white/[0.04]" />
      <div className="h-3 w-20 bg-white/[0.06]" />
      <div className="space-y-2">
        <div className="h-8 bg-white/[0.04]" />
        <div className="h-8 bg-white/[0.04]" />
        <div className="h-8 bg-white/[0.04]" />
      </div>
    </div>
  );
}

export function LoginEnginePreview() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["public-preview"],
    queryFn: fetchPublicPreview,
    staleTime: 60_000,
    refetchInterval: 90_000,
    retry: 1,
  });

  if (isLoading) return <PreviewSkeleton />;

  if (isError || !data) {
    return (
      <div className="surface p-5">
        <p className="label-caps">Engine preview</p>
        <p className="mt-3 text-sm text-muted-foreground">
          Live snapshot unavailable right now. Sign in to open the full dashboard.
        </p>
      </div>
    );
  }

  return (
    <div className="surface overflow-hidden p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="label-caps">Engine preview</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
            Live paper · hot ranks
          </p>
        </div>
        {data.last_tick_at ? (
          <p className="font-mono text-[10px] text-muted-foreground/45">
            tick {new Date(data.last_tick_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
          </p>
        ) : null}
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <MiniLedger title="Optimistic" hint="signal fill" ledger={data.optimistic} />
        <MiniLedger title="Honest" hint="next-bar fill" ledger={data.honest} />
      </div>

      <div className="mt-5">
        <p className="label-caps text-muted-foreground/70">Hot picks</p>
        {data.hot_picks.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Rankings are warming up — check back after the first cache fill.
          </p>
        ) : (
          <ul className="mt-2">
            {data.hot_picks.map((pick) => (
              <PickRow key={pick.symbol} pick={pick} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
