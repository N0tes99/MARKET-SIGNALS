"use client";

import { SetupIdeaCard } from "@/components/setup-idea-card";
import { useSetupsFeed } from "@/hooks/use-setups-feed";

/** Dashboard strip: cross-crypto setup candidates (WATCH-first feed). */
export function OpportunitiesFeed() {
  const { data, isLoading, isError, refetch, isFetching } = useSetupsFeed({
    watchOnly: true,
    minConfidence: 55,
  });

  const setups = data?.setups ?? [];

  return (
    <section className="mb-8 border-b border-white/[0.05] pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Crypto setups</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            watch candidates · not ranked grades
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
          <div className="surface skeleton h-28" />
          <div className="surface skeleton h-28" />
          <div className="surface skeleton h-28 hidden lg:block" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4 flex flex-col items-start gap-2">
          <p className="text-sm text-muted-foreground/60">Feed unavailable</p>
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
          No watch-level setups right now — quiet tape is fine.
        </p>
      ) : null}

      {!isLoading && !isError && setups.length > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {setups.slice(0, 9).map((idea) => (
            <SetupIdeaCard key={idea.id} idea={idea} showSymbol />
          ))}
        </div>
      ) : null}
    </section>
  );
}
