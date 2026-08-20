"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { usePerpsBoard } from "@/hooks/use-perps-board";
import { cn } from "@/lib/utils";
import {
  fetchPaperSummary,
  type PaperTrade,
  type PerpsFundingRow,
  type PerpsIdeaRow,
  type PerpsLiquidationRow,
} from "@/services/api";

const CRYPTO_PAPER_SOURCES = new Set([
  "crypto_perp_v2",
  "crypto_setup",
  "squeeze_expansion",
]);

function money(n: number): string {
  const sign = n > 0 ? "+" : n < 0 ? "" : "";
  return `${sign}${n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  })}`;
}

function usdCompact(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function pnlTone(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-muted-foreground/60";
  return n > 0 ? "text-emerald-300/80" : "text-rose-300/75";
}

function sourceLabel(source: string): string {
  if (source === "crypto_perp_v2") return "perp v2";
  if (source === "crypto_setup") return "crypto L2";
  if (source === "squeeze_expansion") return "expansion";
  return source;
}

function isCryptoPaper(trade: PaperTrade): boolean {
  return CRYPTO_PAPER_SOURCES.has(trade.source);
}

function PaperTradeCard({ trade }: { trade: PaperTrade }) {
  const pnl = trade.optimistic_pnl_usd;
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
          <span className="font-mono text-[10px] text-muted-foreground/40">{trade.status}</span>
        </div>
        <span className={cn("font-mono text-[11px]", pnlTone(pnl))}>
          {pnl != null ? money(pnl) : money(trade.size_usd)}
        </span>
      </div>
      {trade.factors?.length ? (
        <p className="mt-1.5 font-mono text-[10px] leading-relaxed text-muted-foreground/55">
          {trade.factors.slice(0, 3).join(" · ")}
        </p>
      ) : null}
    </li>
  );
}

function FundingMobileCard({ row }: { row: PerpsFundingRow }) {
  return (
    <li className="border-t border-white/[0.05] py-3 first:border-t-0 first:pt-0 md:hidden">
      <div className="flex items-baseline justify-between gap-2">
        <Link
          href={`/assets/${row.symbol}`}
          className="font-mono text-sm underline-offset-2 hover:underline"
        >
          {row.symbol}
        </Link>
        <span className="font-mono text-[11px] text-muted-foreground/70">
          {row.available && row.funding_bps != null
            ? `${row.funding_bps >= 0 ? "+" : ""}${row.funding_bps.toFixed(2)} bps`
            : "—"}
        </span>
      </div>
      <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
        OI Δ {row.oi_change_pct != null ? `${row.oi_change_pct >= 0 ? "+" : ""}${row.oi_change_pct.toFixed(1)}%` : "—"}
        {" · "}
        mark {row.mark_price != null ? row.mark_price.toFixed(2) : "—"}
        {!row.available && row.note ? ` · ${row.note}` : ""}
      </p>
    </li>
  );
}

function LiqMobileCard({ row }: { row: PerpsLiquidationRow }) {
  return (
    <li className="border-t border-white/[0.05] py-3 first:border-t-0 first:pt-0 md:hidden">
      <div className="flex items-baseline justify-between gap-2">
        <Link
          href={`/assets/${row.symbol}`}
          className="font-mono text-sm underline-offset-2 hover:underline"
        >
          {row.symbol}
        </Link>
        <span className="font-mono text-[11px] text-muted-foreground/70">
          {row.available ? usdCompact(row.total_usd) : "—"}
        </span>
      </div>
      <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
        {row.available
          ? `L ${usdCompact(row.long_usd)} / S ${usdCompact(row.short_usd)}`
          : row.description || "unavailable"}
        {row.coinglass_url ? (
          <>
            {" · "}
            <a
              href={row.coinglass_url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline-offset-2 hover:underline"
            >
              Coinglass
            </a>
          </>
        ) : null}
      </p>
    </li>
  );
}

function IdeaCard({ idea }: { idea: PerpsIdeaRow }) {
  return (
    <li className="border-t border-white/[0.05] py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <Link
          href={`/assets/${idea.symbol}`}
          className="font-mono text-sm underline-offset-2 hover:underline"
        >
          {idea.symbol}
        </Link>
        <span className="label-caps text-muted-foreground/55">{idea.setup_type}</span>
        <span className="font-mono text-[10px] text-muted-foreground/45">{idea.direction_bias}</span>
        <span className="font-mono text-[10px] text-muted-foreground/40">
          {idea.confidence.toFixed(0)}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground/35">{idea.trade_state_hint}</span>
      </div>
      {idea.factors.length ? (
        <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
          {idea.factors.slice(0, 3).join(" · ")}
        </p>
      ) : null}
    </li>
  );
}

export default function PerpsPage() {
  const board = usePerpsBoard();
  const paper = useQuery({
    queryKey: ["paper-summary", "perps-tab"],
    queryFn: () => fetchPaperSummary(false),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const openCrypto = (paper.data?.open_trades ?? []).filter(isCryptoPaper);
  const closedCrypto = (paper.data?.recent_closed ?? []).filter(isCryptoPaper);
  const funding = board.data?.funding ?? [];
  const liquidations = board.data?.liquidations ?? [];
  const ideas = board.data?.ideas ?? [];

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Crypto perps" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Paper crypto activity only — Layer-2 setups and perp v2 momentum. Funding comes
          from Bybit when reachable, otherwise OKX (US/Render-safe). Liquidations use recent
          OKX fills (Bybit fallback); Coinglass stays an optional chart deep-link.
          Not live exchange orders. Not financial advice.
        </p>

        <div className="mt-4 flex flex-wrap items-baseline gap-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            {board.data?.funding_source || "funding"}{" "}
            {board.data?.funding_filled ?? 0}/{board.data?.symbols_scanned ?? 0}
            {" · "}
            liqs {board.data?.liquidations_filled ?? 0}
            {" · "}
            paper open {openCrypto.length}
          </p>
          {(board.isFetching || paper.isFetching) && !board.isLoading ? (
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
              refreshing
            </span>
          ) : null}
          <button
            type="button"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => {
              void board.refetch();
              void paper.refetch();
            }}
          >
            Retry
          </button>
        </div>

        {/* Paper activity */}
        <section className="mt-10">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70">
            Paper activity
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground/70">
            Opens and recent closes from <span className="text-muted-foreground">crypto_perp_v2</span>{" "}
            and Layer-2 <span className="text-muted-foreground">crypto_setup</span>. Equity and tape
            stay on the home paper panel.
          </p>
          {paper.isLoading ? (
            <div className="surface mt-4 h-28 animate-pulse" />
          ) : paper.isError ? (
            <p className="mt-4 text-sm text-muted-foreground">Paper summary failed to load.</p>
          ) : (
            <div className="mt-5 grid gap-8 lg:grid-cols-2">
              <div>
                <h3 className="label-caps text-muted-foreground/50">Open</h3>
                {openCrypto.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground/60">No crypto paper open.</p>
                ) : (
                  <ul className="mt-2">
                    {openCrypto.map((t) => (
                      <PaperTradeCard key={t.id} trade={t} />
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h3 className="label-caps text-muted-foreground/50">Recent closed</h3>
                {closedCrypto.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground/60">No recent crypto closes.</p>
                ) : (
                  <ul className="mt-2">
                    {closedCrypto.map((t) => (
                      <PaperTradeCard key={t.id} trade={t} />
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Funding */}
        <section className="mt-14">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70">
            Funding board
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground/70">
            USDT linear perpetuals for the perp-v2 universe (Bybit when reachable, else OKX).
            Sorted by absolute funding.
          </p>
          {board.isLoading ? (
            <div className="surface mt-4 h-40 animate-pulse" />
          ) : board.isError ? (
            <p className="mt-4 text-sm text-muted-foreground">Funding board failed to load.</p>
          ) : (
            <>
              <ul className="mt-4 md:hidden">
                {funding.map((row) => (
                  <FundingMobileCard key={row.symbol} row={row} />
                ))}
              </ul>
              <div className="mt-4 hidden overflow-x-auto md:block">
                <table className="w-full min-w-[640px] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-white/[0.06] font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
                      <th className="py-2 pr-3 font-normal">Symbol</th>
                      <th className="py-2 pr-3 font-normal">Funding</th>
                      <th className="py-2 pr-3 font-normal">Trend</th>
                      <th className="py-2 pr-3 font-normal">OI Δ</th>
                      <th className="py-2 pr-3 font-normal">Mark</th>
                      <th className="py-2 font-normal">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {funding.map((row) => (
                      <tr
                        key={row.symbol}
                        className="border-b border-white/[0.04] font-mono text-[12px] text-muted-foreground/75"
                      >
                        <td className="py-2.5 pr-3">
                          <Link
                            href={`/assets/${row.symbol}`}
                            className="text-foreground/85 underline-offset-2 hover:underline"
                          >
                            {row.symbol}
                          </Link>
                        </td>
                        <td className="py-2.5 pr-3">
                          {row.available && row.funding_bps != null
                            ? `${row.funding_bps >= 0 ? "+" : ""}${row.funding_bps.toFixed(2)} bps`
                            : "—"}
                        </td>
                        <td className="py-2.5 pr-3">
                          {row.funding_trend_bps != null
                            ? `${row.funding_trend_bps >= 0 ? "+" : ""}${row.funding_trend_bps.toFixed(2)}`
                            : "—"}
                        </td>
                        <td className="py-2.5 pr-3">
                          {row.oi_change_pct != null
                            ? `${row.oi_change_pct >= 0 ? "+" : ""}${row.oi_change_pct.toFixed(1)}%`
                            : "—"}
                        </td>
                        <td className="py-2.5 pr-3">
                          {row.mark_price != null ? row.mark_price.toFixed(2) : "—"}
                        </td>
                        <td className="py-2.5">{row.available ? row.source || "okx" : row.note || "miss"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        {/* Liquidations */}
        <section className="mt-14">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70">
            Liquidations
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground/70">
            {board.data?.liquidations_note ??
              "Recent OKX/Bybit long/short liquidations. Coinglass charts stay as a deep-link."}
          </p>
          {board.isLoading ? (
            <div className="surface mt-4 h-40 animate-pulse" />
          ) : board.isError ? (
            <p className="mt-4 text-sm text-muted-foreground">Liquidations failed to load.</p>
          ) : (
            <>
              <ul className="mt-4 md:hidden">
                {liquidations.map((row) => (
                  <LiqMobileCard key={row.symbol} row={row} />
                ))}
              </ul>
              <div className="mt-4 hidden overflow-x-auto md:block">
                <table className="w-full min-w-[640px] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-white/[0.06] font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
                      <th className="py-2 pr-3 font-normal">Symbol</th>
                      <th className="py-2 pr-3 font-normal">Long</th>
                      <th className="py-2 pr-3 font-normal">Short</th>
                      <th className="py-2 pr-3 font-normal">Total</th>
                      <th className="py-2 pr-3 font-normal">Note</th>
                      <th className="py-2 font-normal">Link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {liquidations.map((row) => (
                      <tr
                        key={row.symbol}
                        className="border-b border-white/[0.04] font-mono text-[12px] text-muted-foreground/75"
                      >
                        <td className="py-2.5 pr-3">
                          <Link
                            href={`/assets/${row.symbol}`}
                            className="text-foreground/85 underline-offset-2 hover:underline"
                          >
                            {row.symbol}
                          </Link>
                        </td>
                        <td className="py-2.5 pr-3">{row.available ? usdCompact(row.long_usd) : "—"}</td>
                        <td className="py-2.5 pr-3">{row.available ? usdCompact(row.short_usd) : "—"}</td>
                        <td className="py-2.5 pr-3">{row.available ? usdCompact(row.total_usd) : "—"}</td>
                        <td className="max-w-[280px] py-2.5 pr-3 text-[11px] text-muted-foreground/55">
                          {row.description || "—"}
                        </td>
                        <td className="py-2.5">
                          {row.coinglass_url ? (
                            <a
                              href={row.coinglass_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline-offset-2 hover:underline"
                            >
                              Coinglass
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        {/* Layer-2 ideas */}
        <section className="mt-14">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70">
            Perp ideas
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground/70">
            Live Layer-2 scanners: funding extremes, liquidation flushes, and basis-rich
            names that can feed the paper agent.
          </p>
          {board.isLoading ? (
            <div className="surface mt-4 h-24 animate-pulse" />
          ) : ideas.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground/60">
              No funding_extreme / liq_flush / basis_rich ideas at WATCH confidence right now.
            </p>
          ) : (
            <ul className="mt-4 max-w-2xl">
              {ideas.map((idea) => (
                <IdeaCard key={idea.id} idea={idea} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
