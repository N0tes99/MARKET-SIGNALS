"use client";

import { OptionsTapeCard } from "@/components/options-tape-card";
import { SiteHeader } from "@/components/site-header";
import { useOptionsTape } from "@/hooks/use-options-tape";

export default function TapePage() {
  const { data, isLoading, isError, refetch, isFetching } = useOptionsTape(5);
  const longs = data?.longs ?? [];
  const shorts = data?.shorts ?? [];

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Aggressive tape" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Volume-first options hunter. Longs and shorts are scored independently so
          the board stays two-sided. Universe is the equity watchlist plus Radar
          seeds and extra liquid names — add any US ticker later via the API{" "}
          <span className="font-mono text-[11px]">?add=</span> param. Not orders.
          Not financial advice.
        </p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          <span>scanned {data?.symbols_scanned ?? "—"}</span>
          <span>chained {data?.symbols_optioned ?? "—"}</span>
          {isFetching && !isLoading ? <span>refreshing</span> : null}
        </div>

        {isLoading ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <div className="surface skeleton h-36" />
            <div className="surface skeleton h-36" />
          </div>
        ) : null}

        {isError ? (
          <div className="mt-6 flex flex-col items-start gap-2">
            <p className="text-sm text-muted-foreground/60">Tape feed unavailable</p>
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {!isLoading && !isError ? (
          <div className="mt-8 grid gap-8 lg:grid-cols-2">
            <section>
              <h2 className="label-caps text-bullish/80">Longs · calls</h2>
              <p className="mt-1 mb-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
                rel vol + upside tape + call activity
              </p>
              {longs.length === 0 ? (
                <p className="text-sm text-muted-foreground/50">No long standouts.</p>
              ) : (
                <div className="grid gap-3">
                  {longs.map((hunt) => (
                    <OptionsTapeCard key={hunt.id} hunt={hunt} />
                  ))}
                </div>
              )}
            </section>
            <section>
              <h2 className="label-caps text-bearish/80">Shorts · puts</h2>
              <p className="mt-1 mb-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
                rel vol + downside tape + put activity
              </p>
              {shorts.length === 0 ? (
                <p className="text-sm text-muted-foreground/50">No short standouts.</p>
              ) : (
                <div className="grid gap-3">
                  {shorts.map((hunt) => (
                    <OptionsTapeCard key={hunt.id} hunt={hunt} />
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : null}
      </div>
    </main>
  );
}
