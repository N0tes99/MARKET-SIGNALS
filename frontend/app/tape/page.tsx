"use client";

import { FormEvent, useEffect, useState } from "react";

import { OptionsTapeCard } from "@/components/options-tape-card";
import { SiteHeader } from "@/components/site-header";
import { useOptionsTape } from "@/hooks/use-options-tape";
import { normalizeTapeTicker, readTapeExtras, writeTapeExtras } from "@/lib/tape-extras";

export default function TapePage() {
  const [extras, setExtras] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [hint, setHint] = useState("");
  const { data, isLoading, isError, refetch, isFetching } = useOptionsTape(5, extras);
  const longs = data?.longs ?? [];
  const shorts = data?.shorts ?? [];

  useEffect(() => {
    setExtras(readTapeExtras());
  }, []);

  function persist(next: string[]) {
    setExtras(next);
    writeTapeExtras(next);
  }

  function onAdd(event: FormEvent) {
    event.preventDefault();
    const symbol = normalizeTapeTicker(draft);
    if (!symbol) {
      setHint("US equity ticker, 1–5 letters. Crypto names stay off this board.");
      return;
    }
    if (extras.includes(symbol)) {
      setHint(`${symbol} is already in the extra hunt list.`);
      setDraft("");
      return;
    }
    persist([...extras, symbol]);
    setDraft("");
    setHint(`${symbol} added — next scan includes it.`);
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Aggressive tape" />
      <div className="container mx-auto px-4 pb-16 pt-8">
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Volume-first options hunter. Longs and shorts are scored independently so
          the board stays two-sided. Type any US ticker to force it onto the next
          scan — extras live in this browser. Not orders. Not financial advice.
        </p>

        <form onSubmit={onAdd} className="mt-5 flex flex-wrap items-end gap-2">
          <label className="block">
            <span className="label-caps text-muted-foreground/55">Hunt a ticker</span>
            <input
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value.toUpperCase());
                setHint("");
              }}
              placeholder="NVDA"
              maxLength={5}
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              className="mt-1 block w-28 border border-white/[0.08] bg-transparent px-2 py-1.5 font-mono text-sm uppercase tracking-wide outline-none focus:border-white/25"
            />
          </label>
          <button
            type="submit"
            className="border border-white/[0.12] px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:border-white/25 hover:text-foreground"
          >
            Add
          </button>
          <button
            type="button"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void refetch()}
          >
            {isFetching && !isLoading ? "Refreshing" : "Rescan"}
          </button>
        </form>
        {hint ? (
          <p className="mt-2 font-mono text-[10px] text-muted-foreground/70">{hint}</p>
        ) : null}

        {extras.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2">
            {extras.map((symbol) => (
              <li key={symbol}>
                <button
                  type="button"
                  onClick={() => persist(extras.filter((item) => item !== symbol))}
                  className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:text-foreground hover:underline"
                >
                  {symbol} ×
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
          <span>scanned {data?.symbols_scanned ?? "—"}</span>
          <span>chained {data?.symbols_optioned ?? "—"}</span>
          {extras.length > 0 ? <span>extras {extras.length}</span> : null}
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
