"use client";

import Link from "next/link";

import { OptionsTapeCard } from "@/components/options-tape-card";
import { useOptionsTape } from "@/hooks/use-options-tape";

/** Home strip: equal long / short aggressive options hunts. */
export function OptionsTapeStrip() {
  const { data, isLoading, isError, refetch, isFetching } = useOptionsTape(3);
  const longs = data?.longs ?? [];
  const shorts = data?.shorts ?? [];

  return (
    <section className="mb-6 border-b border-white/[0.05] pb-6 sm:mb-8 sm:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">
            <Link href="/tape" className="underline-offset-2 hover:underline">
              Aggressive tape
            </Link>
          </h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            equal longs + shorts · volume first · open universe
          </p>
        </div>
        {isFetching && !isLoading ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/40">
            refreshing
          </p>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="surface skeleton h-32" />
          <div className="surface skeleton h-32" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4 flex flex-col items-start gap-2">
          <p className="text-sm text-muted-foreground/60">Options tape unavailable</p>
          <button
            type="button"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {!isLoading && !isError && longs.length === 0 && shorts.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground/50">
          No volume standouts with tradeable option structure right now.
        </p>
      ) : null}

      {!isLoading && !isError && (longs.length > 0 || shorts.length > 0) ? (
        <div className="mt-4 grid gap-5 lg:grid-cols-2">
          <div>
            <p className="label-caps mb-2 text-bullish/80">Longs · calls</p>
            <div className="grid gap-3">
              {longs.slice(0, 3).map((hunt) => (
                <OptionsTapeCard key={hunt.id} hunt={hunt} />
              ))}
            </div>
          </div>
          <div>
            <p className="label-caps mb-2 text-bearish/80">Shorts · puts</p>
            <div className="grid gap-3">
              {shorts.slice(0, 3).map((hunt) => (
                <OptionsTapeCard key={hunt.id} hunt={hunt} />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
