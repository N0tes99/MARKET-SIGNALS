"use client";

import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import {
  fetchAlpacaMirror,
  type AlpacaFill,
  type AlpacaPosition,
} from "@/services/api";

function money(n: number, digits = 0): string {
  const sign = n > 0 ? "+" : n < 0 ? "" : "";
  return `${sign}${n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
  })}`;
}

function plainMoney(n: number, digits = 0): string {
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

function pnlTone(n: number): string {
  if (n > 0) return "text-bullish";
  if (n < 0) return "text-bearish";
  return "text-muted-foreground/70";
}

function PositionRow({ p }: { p: AlpacaPosition }) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-white/[0.04] py-2 last:border-0">
      <div>
        <p className="font-mono text-sm tracking-tight text-foreground/90">{p.symbol}</p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          {p.side} · {p.qty} @ {plainMoney(p.avg_entry_price, 2)}
        </p>
      </div>
      <div className="text-right">
        <p className="font-mono text-sm">{plainMoney(p.market_value, 0)}</p>
        <p className={cn("font-mono text-[11px]", pnlTone(p.unrealized_pl))}>
          {money(p.unrealized_pl, 0)} · {pct(p.unrealized_plpc)}
        </p>
      </div>
    </li>
  );
}

function FillRow({ f }: { f: AlpacaFill }) {
  const price = f.filled_avg_price;
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-white/[0.04] py-2 last:border-0">
      <div>
        <p className="font-mono text-sm tracking-tight text-foreground/90">{f.symbol}</p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          {f.side} · {f.qty}
          {price != null ? ` @ ${plainMoney(price, 2)}` : ""}
          {f.order_type ? ` · ${f.order_type}` : ""}
        </p>
      </div>
      <p className="font-mono text-[10px] text-muted-foreground/55">
        {f.filled_at ? new Date(f.filled_at).toLocaleString() : f.status}
      </p>
    </li>
  );
}

/** Read-only Alpaca book mirror — never places orders. */
export function AlpacaMirrorPanel() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["alpaca-mirror"],
    queryFn: fetchAlpacaMirror,
    staleTime: 45_000,
    refetchInterval: 90_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const configured = data?.configured === true;
  const mode = data?.mode ?? "unconfigured";

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Alpaca mirror</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            read-only · positions + fills · no auto-execution
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {configured ? (
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
              {mode}
              {data?.cached ? " · cached" : ""}
            </p>
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
          <div className="surface skeleton h-28" />
          <div className="surface skeleton h-28" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4">
          <p className="text-sm text-muted-foreground/60">Alpaca mirror unavailable</p>
          <button
            type="button"
            className="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {data && !configured ? (
        <div className="mt-4 border border-dashed border-white/[0.08] bg-card/10 px-4 py-5">
          <p className="text-sm text-muted-foreground/70">Alpaca not configured</p>
          <p className="mt-2 max-w-xl font-mono text-[11px] leading-relaxed text-muted-foreground/45">
            Set ALPACA_API_KEY and ALPACA_API_SECRET on the API (optional ALPACA_BASE_URL for
            paper vs live). This panel only mirrors — it never places orders. Keep Robinhood for
            manual trading if you want.
          </p>
        </div>
      ) : null}

      {data && configured ? (
        <>
          {data.error ? (
            <p className="mt-3 font-mono text-[11px] text-bearish/80">{data.error}</p>
          ) : null}

          {data.account ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="surface p-4">
                <p className="label-caps text-muted-foreground/70">Equity</p>
                <p className="mt-2 font-mono text-xl tracking-tight">
                  {plainMoney(data.account.equity, 0)}
                </p>
              </div>
              <div className="surface p-4">
                <p className="label-caps text-muted-foreground/70">Cash</p>
                <p className="mt-2 font-mono text-xl tracking-tight">
                  {plainMoney(data.account.cash, 0)}
                </p>
              </div>
              <div className="surface p-4">
                <p className="label-caps text-muted-foreground/70">Buying power</p>
                <p className="mt-2 font-mono text-xl tracking-tight">
                  {plainMoney(data.account.buying_power, 0)}
                </p>
              </div>
            </div>
          ) : null}

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="label-caps text-muted-foreground/75">
                Positions · {data.positions.length}
              </p>
              {data.positions.length === 0 ? (
                <p className="mt-3 font-mono text-[11px] text-muted-foreground/45">
                  No open Alpaca positions
                </p>
              ) : (
                <ul className="mt-2">
                  {data.positions.map((p) => (
                    <PositionRow key={`${p.symbol}-${p.side}`} p={p} />
                  ))}
                </ul>
              )}
            </div>
            <div>
              <p className="label-caps text-muted-foreground/75">
                Recent fills · {data.recent_fills.length}
              </p>
              {data.recent_fills.length === 0 ? (
                <p className="mt-3 font-mono text-[11px] text-muted-foreground/45">
                  No recent filled orders
                </p>
              ) : (
                <ul className="mt-2">
                  {data.recent_fills.slice(0, 12).map((f) => (
                    <FillRow key={f.id || `${f.symbol}-${f.filled_at}`} f={f} />
                  ))}
                </ul>
              )}
            </div>
          </div>

          <p className="mt-4 font-mono text-[10px] text-muted-foreground/40">
            Mirrored from Alpaca REST · compare with paper agent above · as of{" "}
            {new Date(data.as_of).toLocaleTimeString()}
          </p>
        </>
      ) : null}
    </section>
  );
}
