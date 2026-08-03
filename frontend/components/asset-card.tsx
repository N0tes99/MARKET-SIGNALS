import Link from "next/link";

import { cn } from "@/lib/utils";
import type { AssetSummary } from "@/services/api";

interface AssetCardProps {
  asset: AssetSummary;
}

function trendColor(trend: string): string {
  switch (trend) {
    case "Bullish":
      return "text-bullish";
    case "Bearish":
      return "text-bearish";
    default:
      return "text-neutral";
  }
}

function stateLabel(state: string): string {
  return state.toLowerCase();
}

export function AssetCard({ asset }: AssetCardProps) {
  return (
    <Link href={`/assets/${asset.symbol}`}>
      <article className="surface-interactive group p-5">
        <div className="flex items-start justify-between border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-mono text-lg tracking-wide">{asset.symbol}</h2>
              <span className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {asset.asset_class}
              </span>
            </div>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              {stateLabel(asset.trade_state)} · {asset.execution_signal.toLowerCase()}
            </p>
          </div>
          <span className="font-mono text-sm text-foreground/80">{asset.trade_grade}</span>
        </div>

        <div className="mt-4 space-y-2.5">
          <MetricRow label="Confidence" value={`${asset.confidence.toFixed(0)}%`} />
          <MetricRow
            label="Trend"
            value={asset.trend.toLowerCase()}
            valueClassName={trendColor(asset.trend)}
          />
          <MetricRow label="Momentum" value={`${asset.buyer_strength.toFixed(0)}%`} />
          <MetricRow label="Risk" value={`${asset.risk.toFixed(0)}%`} />
          <MetricRow label="EV" value={asset.expected_value.toFixed(2)} />
        </div>
      </article>
    </Link>
  );
}

function MetricRow({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-baseline justify-between text-sm">
      <span className="label-caps">{label}</span>
      <span className={cn("font-mono text-[13px]", valueClassName ?? "text-foreground/90")}>
        {value}
      </span>
    </div>
  );
}
