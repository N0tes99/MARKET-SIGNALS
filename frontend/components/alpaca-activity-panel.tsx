"use client";

import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import {
  fetchAlpacaActivity,
  type AlpacaActivityRow,
} from "@/services/api";

function plainMoney(n: number, digits = 2): string {
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
  });
}

function pct(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(2)}%`;
}

function vol(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toFixed(0);
}

function tone(n: number | null): string {
  if (n == null) return "text-muted-foreground/70";
  if (n > 0) return "text-bullish";
  if (n < 0) return "text-bearish";
  return "text-muted-foreground/70";
}

function ActivityRow({ row }: { row: AlpacaActivityRow }) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-white/[0.04] py-2 last:border-0">
      <div>
        <p className="font-mono text-sm tracking-tight text-foreground/90">{row.symbol}</p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          {row.daily_volume != null ? `vol ${vol(row.daily_volume)}` : "vol —"}
          {row.trade_time
            ? ` · ${new Date(row.trade_time).toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
              })}`
            : ""}
        </p>
      </div>
      <div className="text-right">
        <p className="font-mono text-sm">
          {row.last_price != null ? plainMoney(row.last_price) : "—"}
        </p>
        <p className={cn("font-mono text-[11px]", tone(row.change_pct))}>
          {row.change_pct != null ? pct(row.change_pct) : "—"}
        </p>
      </div>
    </li>
  );
}

/** Free-tier Alpaca IEX activity for tracked stocks/ETFs — not portfolio mirror. */
export function AlpacaActivityPanel() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["alpaca-activity"],
    queryFn: () => fetchAlpacaActivity(),
    staleTime: 60_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const configured = data?.configured === true;
  const rows = [...(data?.rows ?? [])].sort((a, b) => {
    const av = Math.abs(a.change_pct ?? 0);
    const bv = Math.abs(b.change_pct ?? 0);
    return bv - av;
  });

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Alpaca activity</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            free IEX · last / change / volume · not full tape
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
            {configured ? `${data?.feed ?? "iex"}` : "keys needed"}
            {data?.cached ? " · cached" : ""}
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:underline disabled:opacity-40"
          >
            {isFetching ? "…" : "Refresh"}
          </button>
        </div>
      </div>

      {isLoading && (
        <p className="mt-4 font-mono text-xs text-muted-foreground/60">Loading IEX snapshots…</p>
      )}
      {isError && (
        <p className="mt-4 font-mono text-xs text-bearish">Could not load Alpaca activity.</p>
      )}

      {!isLoading && data && !configured && (
        <p className="mt-4 border border-dashed border-white/[0.08] px-4 py-6 font-mono text-xs text-muted-foreground/65">
          Set <span className="text-foreground/80">ALPACA_API_KEY</span> +{" "}
          <span className="text-foreground/80">ALPACA_API_SECRET</span> on the API to enable free
          IEX activity (Basic plan — no paid SIP).
        </p>
      )}

      {!isLoading && data && configured && data.error && (
        <p className="mt-4 font-mono text-xs text-bearish">{data.error}</p>
      )}

      {!isLoading && data && configured && !data.error && rows.length === 0 && (
        <p className="mt-4 font-mono text-xs text-muted-foreground/60">
          No IEX rows returned (market closed or symbols quiet on IEX).
        </p>
      )}

      {!isLoading && configured && rows.length > 0 && (
        <ul className="mt-4 max-h-80 overflow-y-auto">
          {rows.slice(0, 24).map((row) => (
            <ActivityRow key={row.symbol} row={row} />
          ))}
        </ul>
      )}

      <p className="mt-4 font-mono text-[10px] text-muted-foreground/45">
        Single-exchange IEX feed · free Basic tier · as of{" "}
        {data?.as_of ? new Date(data.as_of).toLocaleTimeString() : "—"}
      </p>
    </section>
  );
}
