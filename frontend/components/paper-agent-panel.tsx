"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";
import {
  fetchPaperSummary,
  resetPaperAgent,
  type PaperLedger,
  type PaperTrade,
} from "@/services/api";

const TRADE_COLLAPSE_AFTER = 5;

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

function LedgerCard({ title, ledger, hint }: { title: string; ledger: PaperLedger; hint: string }) {
  const positive = ledger.total_pnl >= 0;
  const deployed = ledger.deployed_usd ?? 0;
  const sleeve = ledger.size_usd ?? 2500;
  return (
    <div className="surface p-5">
      <p className="label-caps">{title}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
        {hint}
      </p>
      <p
        className={cn(
          "mt-4 font-mono text-2xl tracking-tight",
          positive ? "text-bullish" : "text-bearish",
        )}
      >
        {money(ledger.equity)}
      </p>
      <p className={cn("mt-1 font-mono text-sm", positive ? "text-bullish/80" : "text-bearish/80")}>
        PnL {money(ledger.total_pnl)} · {pct(ledger.return_pct)}
      </p>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/60">
        <span>open {ledger.open_positions}</span>
        <span>deployed {money(deployed)}</span>
        <span>sleeve {money(sleeve)}</span>
        <span>closed {ledger.closed_trades}</span>
        <span>
          W/L {ledger.wins}/{ledger.losses}
        </span>
        <span>real {money(ledger.realized_pnl)}</span>
      </div>
    </div>
  );
}

function TradeRow({ trade }: { trade: PaperTrade }) {
  return (
    <li className="border-t border-white/[0.05] py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <Link
            href={`/assets/${trade.symbol}`}
            className="font-mono text-sm text-foreground/90 underline-offset-2 hover:underline"
          >
            {trade.symbol}
          </Link>
          <span className="label-caps text-muted-foreground/55">{trade.setup_type}</span>
          <span className="font-mono text-[10px] text-muted-foreground/45">{trade.direction}</span>
          <span className="font-mono text-[10px] text-muted-foreground/45">
            {money(trade.size_usd)}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/40">{trade.status}</span>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground/50">
          {new Date(trade.signal_at).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <p className="mt-1.5 font-mono text-[11px] text-muted-foreground/70">
        opt {trade.optimistic_entry.toFixed(4)}
        {trade.optimistic_pnl_usd != null
          ? ` → ${money(trade.optimistic_pnl_usd)} (${trade.optimistic_return_pct?.toFixed(1)}%)`
          : ""}
        {" · "}
        honest{" "}
        {trade.honest_entry != null
          ? `${trade.honest_entry.toFixed(4)}${
              trade.honest_bar_ts
                ? ` @ ${new Date(trade.honest_bar_ts).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`
                : ""
            }`
          : "pending next bar"}
        {trade.honest_pnl_usd != null
          ? ` → ${money(trade.honest_pnl_usd)} (${trade.honest_return_pct?.toFixed(1)}%)`
          : ""}
      </p>
    </li>
  );
}

function TradeLists({
  openTrades,
  closedTrades,
}: {
  openTrades: PaperTrade[];
  closedTrades: PaperTrade[];
}) {
  return (
    <div className="mt-5 grid gap-6 lg:grid-cols-2">
      <div>
        <p className="label-caps text-muted-foreground/55">Open</p>
        <ul className="mt-2">
          {openTrades.length === 0 ? (
            <li className="font-mono text-[11px] text-muted-foreground/45">No open paper</li>
          ) : (
            openTrades.map((t) => <TradeRow key={t.id} trade={t} />)
          )}
        </ul>
      </div>
      <div>
        <p className="label-caps text-muted-foreground/55">Recent closed</p>
        <ul className="mt-2">
          {closedTrades.length === 0 ? (
            <li className="font-mono text-[11px] text-muted-foreground/45">No closed paper yet</li>
          ) : (
            closedTrades.map((t) => <TradeRow key={t.id} trade={t} />)
          )}
        </ul>
      </div>
    </div>
  );
}

/** Public living paper agent — dual ledger PnL everyone can audit. */
export function PaperAgentPanel() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [tradesOpen, setTradesOpen] = useState(false);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["paper-summary"],
    queryFn: () => fetchPaperSummary(true),
    staleTime: 60_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const resetMutation = useMutation({
    mutationFn: resetPaperAgent,
    onSuccess: (summary) => {
      queryClient.setQueryData(["paper-summary"], summary);
      setTradesOpen(false);
    },
  });

  const tradeCount = data
    ? data.open_trades.length + data.recent_closed.length
    : 0;
  const collapseTrades = tradeCount > TRADE_COLLAPSE_AFTER;

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Paper agent</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            living bot · paper only · dual fills · public track record
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {user?.is_admin ? (
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:text-foreground hover:underline disabled:opacity-40"
              disabled={resetMutation.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    "Reset paper agent to $15,000 on both ledgers and clear all trades?",
                  )
                ) {
                  resetMutation.mutate();
                }
              }}
            >
              {resetMutation.isPending ? "resetting…" : "reset $15k"}
            </button>
          ) : null}
          {isFetching && !isLoading ? (
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
              ticking
            </p>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="surface skeleton h-36" />
          <div className="surface skeleton h-36" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4">
          <p className="text-sm text-muted-foreground/60">Paper agent unavailable</p>
          <button
            type="button"
            className="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {resetMutation.isError ? (
        <p className="mt-2 font-mono text-[10px] text-bearish/80">Reset failed — admin session required</p>
      ) : null}

      {data ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <LedgerCard
              title="Optimistic"
              ledger={data.optimistic}
              hint="Fill at signal-time last (+ slip)"
            />
            <LedgerCard
              title="Honest"
              ledger={data.honest}
              hint="Fill at next 15m bar open (+ slip)"
            />
          </div>

          <p className="mt-3 font-mono text-[10px] text-muted-foreground/45">
            Starting {money(data.starting_cash)} paper · each idea locks {money(data.optimistic.size_usd ?? 2500)}{" "}
            notional (equity only moves with PnL) · max {Math.floor(data.starting_cash / (data.optimistic.size_usd ?? 2500))} open ·
            TP +8% / SL −4% · max hold 5d
            {data.last_tick_at
              ? ` · last tick ${new Date(data.last_tick_at).toLocaleTimeString()}`
              : ""}
          </p>

          {tradeCount > 0 ? (
            collapseTrades ? (
              <div className="mt-5">
                <button
                  type="button"
                  className="flex w-full items-baseline justify-between gap-3 border border-white/[0.06] bg-card/20 px-3 py-2.5 text-left backdrop-blur-sm transition-colors hover:border-white/[0.1] hover:bg-card/30"
                  aria-expanded={tradesOpen}
                  onClick={() => setTradesOpen((v) => !v)}
                >
                  <span className="label-caps text-muted-foreground/85">
                    Trades · {tradeCount}
                  </span>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
                    {tradesOpen ? "collapse" : "expand"}
                  </span>
                </button>
                {tradesOpen ? (
                  <TradeLists
                    openTrades={data.open_trades}
                    closedTrades={data.recent_closed}
                  />
                ) : null}
              </div>
            ) : (
              <TradeLists openTrades={data.open_trades} closedTrades={data.recent_closed} />
            )
          ) : null}
        </>
      ) : null}
    </section>
  );
}
