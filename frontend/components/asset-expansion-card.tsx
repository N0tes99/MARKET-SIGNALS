"use client";

import Link from "next/link";

import { useCortexMemory, useExpansionSymbol } from "@/hooks/use-expansion";
import { cn } from "@/lib/utils";

function stateTone(state: string): string {
  switch (state) {
    case "primed":
      return "text-amber-200/80";
    case "triggering":
      return "text-orange-300/85";
    case "expanding":
      return "text-bullish";
    default:
      return "text-muted-foreground";
  }
}

/** Parallel Surface 5 read on asset detail — does not change 13-category grades. */
export function AssetExpansionCard({ symbol }: { symbol: string }) {
  const { data, isLoading, isError } = useExpansionSymbol(symbol);
  const cortexQuery = useCortexMemory();
  const cortex = cortexQuery.data?.symbols.find(
    (ctx) => ctx.symbol.toUpperCase() === symbol.toUpperCase(),
  );
  const specialistBits = (cortex?.opinions ?? [])
    .filter((op) => op.specialist !== "expansion")
    .map((op) => `${op.specialist} ${op.score == null ? "—" : op.score.toFixed(0)}`)
    .slice(0, 4);

  if (isLoading) {
    return <div className="surface skeleton h-28" />;
  }
  if (isError || data == null) {
    return null;
  }
  const notable =
    data.state !== "dormant" || data.trigger_active || data.net_score >= 60;
  if (!notable) {
    return null;
  }

  return (
    <section className="surface p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="label-caps">Expansion</h2>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            cortex specialist · not a grade override
          </p>
        </div>
        <Link
          href="/expansion"
          className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:text-foreground hover:underline"
        >
          radar
        </Link>
      </div>
      <div className="mt-4 flex flex-wrap items-baseline justify-between gap-2">
        <span className={cn("font-mono text-sm uppercase tracking-widest", stateTone(data.state))}>
          {data.state}
        </span>
        <span className="font-mono text-[11px] text-muted-foreground/70">
          net {data.net_score.toFixed(0)} · {data.direction_bias}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-3 font-mono text-[11px]">
        <div>
          <dt className="text-muted-foreground/55">Compress</dt>
          <dd className="mt-0.5 text-foreground/85">{data.compression.score.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground/55">Squeeze</dt>
          <dd className="mt-0.5 text-foreground/85">{data.squeeze.score.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground/55">Trigger</dt>
          <dd className="mt-0.5 text-foreground/85">{data.trigger_active ? "active" : "off"}</dd>
        </div>
      </dl>
      {data.key_trigger ? (
        <p className="mt-3 font-mono text-[11px] text-muted-foreground/65">{data.key_trigger}</p>
      ) : null}
      {specialistBits.length > 0 ? (
        <p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
          {specialistBits.join(" · ")}
        </p>
      ) : null}
      {cortex?.synthesis_notes[0] ? (
        <p className="mt-2 font-mono text-[11px] text-muted-foreground/60">{cortex.synthesis_notes[0]}</p>
      ) : null}
    </section>
  );
}
