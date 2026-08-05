"use client";

import { useBacktest } from "@/hooks/use-backtest";

interface BacktestPanelProps {
  symbol: string;
}

export function BacktestPanel({ symbol }: BacktestPanelProps) {
  const { data, isLoading, error } = useBacktest(symbol);

  if (isLoading) {
    return (
      <div className="surface p-5 lg:col-span-2">
        <div className="h-20 animate-pulse bg-muted/30" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface p-5 lg:col-span-2">
        <h2 className="label-caps">Backtest</h2>
        <p className="mt-3 text-sm text-muted-foreground">Unable to load.</p>
      </div>
    );
  }

  return (
    <div className="surface p-5 lg:col-span-2">
      <div className="flex items-baseline justify-between">
        <h2 className="label-caps">Backtest</h2>
        <span className="font-mono text-[10px] text-muted-foreground">
          {data.hold_bars}h hold · ≥{data.signal_threshold}% signal
        </span>
      </div>

      <p className="mt-3 text-sm text-muted-foreground">{data.description}</p>

      <div className="mt-4 grid grid-cols-2 gap-4 border-t border-white/[0.06] pt-4 sm:grid-cols-4">
        <Stat label="Signals" value={String(data.total_signals)} />
        <Stat label="Win rate" value={`${data.win_rate}%`} />
        <Stat label="Avg return" value={`${data.avg_return_pct > 0 ? "+" : ""}${data.avg_return_pct}%`} />
        <Stat label="Best / Worst" value={`${data.best_return_pct}% / ${data.worst_return_pct}%`} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label-caps">{label}</p>
      <p className="mt-1 font-mono text-sm">{value}</p>
    </div>
  );
}
