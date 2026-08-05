"use client";

import { useDecision } from "@/hooks/use-decision";

interface DecisionBannerProps {
  symbol: string;
}

function stateColor(state: string): string {
  switch (state) {
    case "EXECUTE":
      return "text-bullish";
    case "WATCH":
      return "text-neutral";
    case "IGNORE":
      return "text-muted-foreground";
    default:
      return "text-foreground";
  }
}

export function DecisionBanner({ symbol }: DecisionBannerProps) {
  const { data, isLoading } = useDecision(symbol);

  if (isLoading || !data) {
    return <div className="surface mt-8 h-20 animate-pulse" />;
  }

  return (
    <div className="surface mt-8 p-5">
      <div className="flex flex-wrap gap-x-10 gap-y-4">
        <Stat label="State" value={data.trade_state.toLowerCase()} className={stateColor(data.trade_state)} />
        <Stat label="Grade" value={data.trade_grade} />
        <Stat label="Signal" value={data.execution.signal.toLowerCase()} />
        {data.risk && (
          <Stat label="R:R" value={`${data.risk.risk_reward_ratio.toFixed(1)}:1`} />
        )}
      </div>
      <p className="mt-4 border-t border-white/[0.06] pt-4 text-sm leading-relaxed text-muted-foreground">
        {data.summary}
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <p className="label-caps">{label}</p>
      <p className={`mt-1 font-mono text-sm ${className ?? "text-foreground/90"}`}>{value}</p>
    </div>
  );
}
