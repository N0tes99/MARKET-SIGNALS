"use client";

import { useApplyWeights, useWeightTuning } from "@/hooks/use-weight-tuning";

interface WeightTuningPanelProps {
  symbol: string;
}

export function WeightTuningPanel({ symbol }: WeightTuningPanelProps) {
  const { data, isLoading, error } = useWeightTuning(symbol);
  const apply = useApplyWeights(symbol);

  if (isLoading) {
    return (
      <div className="surface p-5 lg:col-span-2">
        <div className="h-24 animate-pulse bg-muted/30" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface p-5 lg:col-span-2">
        <h2 className="label-caps">Weight tuning</h2>
        <p className="mt-3 text-sm text-muted-foreground">Unable to load.</p>
      </div>
    );
  }

  const isActive = data.active_preset === data.recommended_preset;

  return (
    <div className="surface p-5 lg:col-span-2">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="label-caps">Weight tuning</h2>
        <span className="font-mono text-[10px] text-muted-foreground">
          active: {data.active_preset}
        </span>
      </div>

      <p className="mt-3 text-sm text-muted-foreground">
        Best preset on recent history:{" "}
        <span className="font-mono text-foreground/90">{data.recommended_preset}</span>
        {data.results[0] && (
          <>
            {" "}
            — {data.results[0].win_rate}% win, {data.results[0].avg_return_pct > 0 ? "+" : ""}
            {data.results[0].avg_return_pct}% avg ({data.results[0].total_signals} signals)
          </>
        )}
      </p>

      <div className="mt-4 grid gap-2 border-t border-white/[0.06] pt-4 sm:grid-cols-2">
        {data.results.slice(0, 4).map((row) => (
          <div key={row.preset_name} className="flex justify-between font-mono text-xs">
            <span className={row.preset_name === data.recommended_preset ? "text-foreground" : "text-muted-foreground"}>
              {row.preset_name}
            </span>
            <span className="text-muted-foreground">
              {row.win_rate}% · {row.avg_return_pct > 0 ? "+" : ""}{row.avg_return_pct}%
            </span>
          </div>
        ))}
      </div>

      {!isActive && (
        <button
          type="button"
          onClick={() => apply.mutate(data.recommended_preset)}
          disabled={apply.isPending}
          className="mt-4 border border-white/[0.1] px-4 py-2 font-mono text-xs uppercase tracking-widest transition-colors hover:border-white/[0.2] hover:bg-white/[0.06] disabled:opacity-50"
        >
          {apply.isPending ? "Applying…" : `Apply ${data.recommended_preset}`}
        </button>
      )}
    </div>
  );
}
