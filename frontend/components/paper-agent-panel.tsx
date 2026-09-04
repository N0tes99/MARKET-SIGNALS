"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";
import {
  downloadPaperTradesCsv,
  fetchPaperSummary,
  resetPaperAgent,
  type PaperLedger,
  type PaperMaturity,
  type PaperTrade,
} from "@/services/api";

const TRADE_COLLAPSE_AFTER = 5;

function lastTickMeta(iso: string | null): { text: string; stale: boolean } {
  if (!iso) return { text: "no tick yet", stale: true };
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (min < 2) return { text: "just now", stale: false };
  if (min < 60) return { text: `${min}m ago`, stale: min > 15 };
  return { text: `${Math.round(min / 60)}h ago`, stale: true };
}

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

function MaturityBar({ maturity }: { maturity: PaperMaturity }) {
  return (
    <div className="mt-4 border border-white/[0.06] bg-card/15 px-3 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="label-caps text-muted-foreground/70">Training memory</p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          {maturity.ready_for_private_live
            ? "private live unlock met"
            : `${maturity.score_pct.toFixed(0)}% sample density`}
        </p>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden bg-white/[0.06]">
        <div
          className="h-full bg-foreground/55 transition-[width] duration-500"
          style={{ width: `${Math.min(100, Math.max(0, maturity.score_pct))}%` }}
        />
      </div>
      <p className="mt-2 font-mono text-[10px] text-muted-foreground/55">
        honest closes {maturity.honest_closed}/{maturity.target_honest_closed}
        {" · "}
        memory {maturity.memory_outcomes}/{maturity.target_memory_outcomes}
        {" · "}
        W/R {maturity.win_rate.toFixed(0)}% · avg {pct(maturity.avg_return_pct)}
        {" · "}
        DD {maturity.max_drawdown_pct.toFixed(1)}%
        {maturity.blockers.length > 0
          ? ` · blockers ${maturity.blockers.slice(0, 3).join(", ")}`
          : ""}
      </p>
    </div>
  );
}

function LedgerCard({ title, ledger, hint }: { title: string; ledger: PaperLedger; hint: string }) {
  const deployed = ledger.deployed_usd ?? 0;
  const sleeve = ledger.size_usd ?? 2500;
  return (
    <div className="surface p-5">
      <p className="label-caps">{title}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
        {hint}
      </p>
      <p className={cn("mt-4 font-mono text-2xl tracking-tight", pnlTone(ledger.total_pnl))}>
        {money(ledger.equity)}
      </p>
      <p className={cn("mt-1 font-mono text-sm", pnlTone(ledger.total_pnl))}>
        Total {money(ledger.total_pnl)} · {pct(ledger.return_pct)}
      </p>
      <p className="mt-1 font-mono text-[11px] text-muted-foreground/65">
        <span className={pnlTone(ledger.realized_pnl)}>
          Closed {money(ledger.realized_pnl)}
        </span>
        <span className="text-muted-foreground/40"> · </span>
        <span className={pnlTone(ledger.unrealized_pnl)}>
          Open {money(ledger.unrealized_pnl)}
        </span>
        <span className="text-muted-foreground/40">
          {" "}
          (total = closed + open)
        </span>
      </p>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/60">
        <span>open {ledger.open_positions}</span>
        <span>deployed {money(deployed)}</span>
        <span>sleeve {money(sleeve)}</span>
        <span>closed {ledger.closed_trades}</span>
        <span>
          W/L {ledger.wins}/{ledger.losses}
        </span>
      </div>
    </div>
  );
}

function sourceLabel(source: string): string {
  if (source === "crypto_perp_v2") return "perp v2";
  if (source === "crypto_setup") return "crypto";
  if (source === "equity_setup") return "equity";
  if (source === "tape_hunt") return "tape";
  if (source === "cme_futures") return "cme";
  if (source === "squeeze_expansion") return "expansion";
  return source;
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
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
            {sourceLabel(trade.source)}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/45">{trade.direction}</span>
          <span className="font-mono text-[10px] text-muted-foreground/45">
            {money(trade.size_usd)}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/40">{trade.status}</span>
          {trade.take_profit_pct != null && trade.stop_loss_pct != null ? (
            <span className="font-mono text-[10px] text-muted-foreground/40">
              TP +{trade.take_profit_pct.toFixed(1)}% / SL −{trade.stop_loss_pct.toFixed(1)}%
            </span>
          ) : null}
          {trade.close_reason ? (
            <span className="font-mono text-[10px] text-muted-foreground/40">
              {trade.close_reason}
            </span>
          ) : null}
          {typeof trade.policy?.policy_id === "string" ? (
            <span
              className="font-mono text-[10px] text-muted-foreground/35"
              title="Frozen bot knobs — same id means the same parameters"
            >
              {trade.policy.policy_id}
            </span>
          ) : null}
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
      {trade.stamp ? (
        <p className="mt-1.5 font-mono text-[11px] text-amber-200/70">{trade.stamp}</p>
      ) : null}
      <p className="mt-1.5 font-mono text-[11px] text-muted-foreground/70">
        opt {trade.optimistic_entry.toFixed(4)}
        {trade.optimistic_pnl_usd != null ? (
          <>
            {" → "}
            <span className={pnlTone(trade.optimistic_pnl_usd)}>
              {money(trade.optimistic_pnl_usd)} ({trade.optimistic_return_pct?.toFixed(1)}%)
            </span>
          </>
        ) : null}
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
        {trade.honest_pnl_usd != null ? (
          <>
            {" → "}
            <span className={pnlTone(trade.honest_pnl_usd)}>
              {money(trade.honest_pnl_usd)} ({trade.honest_return_pct?.toFixed(1)}%)
            </span>
          </>
        ) : null}
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
        <p className="label-caps text-muted-foreground/55">Closed / closing</p>
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
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState(false);

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["paper-summary"],
    // Background reads must not tick the agent — tick is a side effect.
    queryFn: () => fetchPaperSummary(false),
    staleTime: 60_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  // One opportunistic tick after rankings start — keep-warm also ticks.
  // 8s so /assets rank_all does not share the 512MB dyno with paper discover.
  useEffect(() => {
    let cancelled = false;
    const run = () => {
      void queryClient
        .fetchQuery({
          queryKey: ["paper-summary"],
          queryFn: () => fetchPaperSummary(true),
        })
        .catch(() => {
          /* keep read-only summary if tick fails */
        });
    };
    let idleId: number | undefined;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      idleId = window.requestIdleCallback(
        () => {
          if (!cancelled) run();
        },
        { timeout: 8_000 },
      );
    } else {
      timeoutId = setTimeout(() => {
        if (!cancelled) run();
      }, 8_000);
    }
    return () => {
      cancelled = true;
      if (timeoutId != null) clearTimeout(timeoutId);
      if (idleId != null && typeof window !== "undefined" && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleId);
      }
    };
  }, [queryClient]);

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
    <section className="mb-6 border-b border-white/[0.05] pb-6 sm:mb-8 sm:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Paper agent</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            public proof track · dual fills · daily open cap
            {" · "}
            <Link href="/rail" className="underline-offset-2 hover:underline">
              open clerk on Rail
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {user?.is_admin ? (
            <>
              <button
                type="button"
                className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:text-foreground hover:underline disabled:opacity-40"
                disabled={csvBusy}
                onClick={() => {
                  setCsvError(false);
                  setCsvBusy(true);
                  void downloadPaperTradesCsv()
                    .catch(() => setCsvError(true))
                    .finally(() => setCsvBusy(false));
                }}
              >
                {csvBusy ? "exporting…" : "export csv"}
              </button>
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
            </>
          ) : null}
          {isFetching && !isLoading ? (
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
              refreshing
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
            onClick={() =>
              void queryClient.fetchQuery({
                queryKey: ["paper-summary"],
                queryFn: () => fetchPaperSummary(true),
              })
            }
          >
            Retry
          </button>
        </div>
      ) : null}

      {csvError ? (
        <p className="mt-2 font-mono text-[10px] text-bearish/80">CSV export failed</p>
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
            notional · max{" "}
            {Math.floor(data.starting_cash / (data.optimistic.size_usd ?? 2500))} concurrent ·{" "}
            {Math.max(0, (data.daily_open_cap ?? 5) - (data.opens_today ?? 0))} of{" "}
            {data.daily_open_cap ?? 5} daily opens left · ATR TP/SL from RiskEngine · max hold 3d
            · WATCH 55 + grade B + F&G + R:R · no US cash Sat/Sun ET
            {" · last tick "}
            <span
              className={
                data.tick_stale || lastTickMeta(data.last_tick_at).stale
                  ? "text-muted-foreground/70"
                  : ""
              }
            >
              {lastTickMeta(data.last_tick_at).text}
            </span>
            {data.tick_stale ? (
              <>
                {" · tick stale — leftover opens still manage, no new opens until fresh"}
              </>
            ) : null}
            {data.paused_new_opens && data.paused_new_opens.length > 0 ? (
              <>
                {" · new opens paused "}
                {data.paused_new_opens.join(", ")}
                {" (perp v2 sleeve)"}
              </>
            ) : null}
          </p>
          {data.tick_notes?.some(
            (n) => n.startsWith("skip:") || n === "discover:skipped",
          ) ? (
            <p className="mt-1 font-mono text-[10px] text-muted-foreground/40">
              {data.tick_notes
                .filter((n) => n.startsWith("skip:") || n === "discover:skipped")
                .slice(0, 4)
                .join(" · ")}
            </p>
          ) : null}

          {data.maturity ? <MaturityBar maturity={data.maturity} /> : null}
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
