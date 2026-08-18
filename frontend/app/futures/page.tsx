"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { useFuturesBoard } from "@/hooks/use-futures-board";
import { cn } from "@/lib/utils";
import { fetchPaperSummary, type CmeFuturesGroup, type CmeFuturesRow } from "@/services/api";

const GROUPS: { key: CmeFuturesGroup | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "index", label: "Index" },
  { key: "energy", label: "Energy" },
  { key: "metals", label: "Metals" },
  { key: "rates", label: "Rates" },
  { key: "fx", label: "FX" },
  { key: "grains", label: "Grains" },
  { key: "crypto", label: "CME crypto" },
];

function formatPct(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

function formatLast(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (Math.abs(value) >= 10) {
    return value.toFixed(2);
  }
  return value.toFixed(4);
}

function formatCompact(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatExpiry(value: string | null | undefined): string {
  if (!value) return "—";
  const day = value.slice(0, 10);
  return day || "—";
}

function pctTone(value: number | null | undefined): string {
  if (value == null || value === 0) return "text-muted-foreground/70";
  return value > 0 ? "text-emerald-300/80" : "text-rose-300/75";
}

function scanLabel(iso: string | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function FuturesMobileCard({ row }: { row: CmeFuturesRow }) {
  return (
    <li className="border-t border-white/[0.05] py-3 first:border-t-0 first:pt-0 md:hidden">
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-sm text-foreground/90">{row.symbol}</p>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
            {row.group} · {row.name}
          </p>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          {row.bucket}
        </span>
      </div>
      <p className="mt-1.5 font-mono text-[11px] text-muted-foreground/70">
        <span className={pctTone(row.change_pct)}>
          {formatLast(row.last)} {formatPct(row.change_pct)}
        </span>
        {" · "}
        vol {formatCompact(row.volume)}
        {" · "}
        oi {formatCompact(row.open_interest)}
      </p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
        12h {formatPct(row.mom_12h_pct, 1)} · score {row.score.toFixed(0)} · exp{" "}
        {formatExpiry(row.expiry)}
      </p>
    </li>
  );
}

export default function FuturesPage() {
  const board = useFuturesBoard();
  const paper = useQuery({
    queryKey: ["paper-summary", "futures-tab"],
    queryFn: () => fetchPaperSummary(false),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  const [group, setGroup] = useState<CmeFuturesGroup | "all">("all");
  const rows = useMemo(() => {
    const all = board.data?.rows ?? [];
    const filtered = group === "all" ? all : all.filter((row) => row.group === group);
    return [...filtered].sort((a, b) => b.score - a.score);
  }, [board.data?.rows, group]);

  const openCme = (paper.data?.open_trades ?? []).filter((t) => t.source === "cme_futures");
  const closedCme = (paper.data?.recent_closed ?? []).filter((t) => t.source === "cme_futures");
  const resolvedCme = closedCme.filter((t) => t.honest_pnl_usd != null);
  const cmePaperN = resolvedCme.length;
  const cmeWinRate =
    cmePaperN > 0
      ? Math.round(
          (resolvedCme.filter((t) => (t.honest_pnl_usd ?? 0) > 0).length / cmePaperN) * 100,
        )
      : null;
  const openCmeLine =
    openCme.length === 0
      ? "none"
      : openCme.map((t) => `${t.symbol} ${t.direction}`).join(" · ");

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Futures" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Yahoo Finance continuous front-month contracts (ES=F, NQ=F, CL=F, GC=F, …). Quotes are
          delayed — this is not a live CME pit or Rithmic feed. Open interest is a published
          level when Yahoo has it, not a live pit print. Not financial advice.
        </p>

        <div className="mt-4 flex flex-wrap items-baseline gap-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            yahoo delayed · {board.data?.symbols_scanned ?? 0} contracts · scanned{" "}
            {scanLabel(board.data?.scanned_at)}
          </p>
          {board.isFetching && !board.isLoading ? (
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
              refreshing
            </span>
          ) : null}
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            paper open {openCmeLine}
            {" · "}
            {cmePaperN > 0
              ? `cme momentum ${cmePaperN} paper · ${cmeWinRate ?? 0}% win`
              : "learning from paper"}
          </p>
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

        <div className="mt-6 inline-flex flex-wrap border border-white/[0.08]">
          {GROUPS.map((item) => {
            const active = group === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setGroup(item.key)}
                className={cn(
                  "px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
                  active
                    ? "bg-white/[0.08] text-foreground"
                    : "text-muted-foreground/60 hover:text-muted-foreground",
                )}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        {board.isLoading ? <div className="surface mt-6 h-40 animate-pulse" /> : null}

        {board.isError ? (
          <div className="mt-6 flex flex-col items-start gap-2">
            <p className="text-sm text-muted-foreground/60">Futures board unavailable</p>
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void board.refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {!board.isLoading && !board.isError && rows.length === 0 ? (
          <p className="mt-6 text-sm text-muted-foreground/60">
            No contracts in this group right now.
          </p>
        ) : null}

        {!board.isLoading && !board.isError && rows.length > 0 ? (
          <>
            <ul className="mt-6 md:hidden">
              {rows.map((row) => (
                <FuturesMobileCard key={row.id} row={row} />
              ))}
            </ul>
            <div className="mt-6 hidden overflow-x-auto md:block">
              <table className="w-full min-w-[720px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-white/[0.06] font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
                    <th className="py-2 pr-3 font-normal">Group</th>
                    <th className="py-2 pr-3 font-normal">Contract</th>
                    <th className="py-2 pr-3 font-normal">Last</th>
                    <th className="py-2 pr-3 font-normal">Change %</th>
                    <th className="py-2 pr-3 font-normal">Volume</th>
                    <th className="py-2 pr-3 font-normal">OI</th>
                    <th className="py-2 pr-3 font-normal">Expiry</th>
                    <th className="py-2 pr-3 font-normal">12h</th>
                    <th className="py-2 pr-3 font-normal">Score</th>
                    <th className="py-2 font-normal">Bucket</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-white/[0.04] font-mono text-[12px] text-muted-foreground/75"
                    >
                      <td className="py-2.5 pr-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
                        {row.group}
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className="text-foreground/85">{row.symbol}</span>
                        <span className="ml-2 text-[11px] text-muted-foreground/50">
                          {row.name}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">{formatLast(row.last)}</td>
                      <td className={cn("py-2.5 pr-3", pctTone(row.change_pct))}>
                        {formatPct(row.change_pct)}
                      </td>
                      <td className="py-2.5 pr-3">{formatCompact(row.volume)}</td>
                      <td className="py-2.5 pr-3">{formatCompact(row.open_interest)}</td>
                      <td className="py-2.5 pr-3">{formatExpiry(row.expiry)}</td>
                      <td className={cn("py-2.5 pr-3", pctTone(row.mom_12h_pct))}>
                        {formatPct(row.mom_12h_pct, 1)}
                      </td>
                      <td className="py-2.5 pr-3">{row.score.toFixed(0)}</td>
                      <td className="py-2.5 font-mono text-[10px] uppercase tracking-widest">
                        {row.bucket}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}
