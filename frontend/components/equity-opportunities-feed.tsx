"use client";

import { EquitySetupCard } from "@/components/equity-setup-card";
import { useEquitySetupsFeed } from "@/hooks/use-equity-setups-feed";

/** Dashboard strip: Layer 3 equity-options setups with staged plans. */
export function EquityOpportunitiesFeed() {
  const { data, isLoading, isError, refetch, isFetching } = useEquitySetupsFeed({
    watchOnly: true,
    minConfidence: 55,
  });

  const setups = data?.setups ?? [];

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Equity options</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            layer 3 · convexity + staged plans · watch only
          </p>
        </div>
        {isFetching && !isLoading ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
            refreshing
          </p>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="surface skeleton h-36" />
          <div className="surface skeleton h-36" />
          <div className="surface skeleton h-36 hidden lg:block" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4 flex flex-col items-start gap-2">
          <p className="text-sm text-muted-foreground/60">Equity options feed unavailable</p>
          <button
            type="button"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {!isLoading && !isError && setups.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground/50">
          No watch-level equity options setups — waiting for momentum + structure.
        </p>
      ) : null}

      {!isLoading && !isError && setups.length > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {setups.slice(0, 6).map((idea) => (
            <EquitySetupCard key={idea.id} idea={idea} showSymbol showPlan />
          ))}
        </div>
      ) : null}
    </section>
  );
}
