import Link from "next/link";

import { TickerMiniChart } from "@/components/ticker-mini-chart";
import { cn } from "@/lib/utils";
import type { AssetQuote, AssetSummary } from "@/services/api";

interface AssetCardProps {
  asset: AssetSummary;
  quote?: AssetQuote | null;
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

function formatPrice(price: number): string {
  if (price >= 1000) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (price >= 1) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
  }
  return price.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 8,
  });
}

function formatChange(changePct: number): string {
  const sign = changePct > 0 ? "+" : "";
  return `${sign}${changePct.toFixed(2)}%`;
}

export function AssetCard({ asset, quote }: AssetCardProps) {
  const change = quote?.change_pct;
  const changeClass =
    change == null
      ? "text-muted-foreground"
      : change > 0
        ? "text-bullish"
        : change < 0
          ? "text-bearish"
          : "text-neutral";

  return (
    <article className="surface-interactive group relative p-5">
      <div className="flex items-start justify-between border-b border-white/[0.06] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <TickerMiniChart symbol={asset.symbol} />
            <span className="rounded-md border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {asset.asset_class}
            </span>
          </div>
          <Link href={`/assets/${asset.symbol}`} className="mt-1 block">
            <p className="font-mono text-[11px] text-muted-foreground transition-colors group-hover:text-foreground/80">
              {stateLabel(asset.trade_state)} · {asset.execution_signal.toLowerCase()}
            </p>
            {quote?.available && quote.price != null ? (
              <p className="mt-2 flex items-baseline gap-2 font-mono text-sm">
                <span className="text-foreground/90">${formatPrice(quote.price)}</span>
                {change != null ? (
                  <span className={cn("text-[11px]", changeClass)}>{formatChange(change)}</span>
                ) : null}
              </p>
            ) : (
              <p className="mt-2 font-mono text-[11px] text-muted-foreground/70">price …</p>
            )}
          </Link>
        </div>
        <Link
          href={`/assets/${asset.symbol}`}
          className="font-mono text-sm text-foreground/80 hover:text-foreground"
        >
          {asset.trade_grade}
        </Link>
      </div>

      <Link href={`/assets/${asset.symbol}`} className="mt-4 block space-y-2.5">
        <MetricRow label="Confidence" value={`${asset.confidence.toFixed(0)}%`} />
        <MetricRow
          label="Trend"
          value={asset.trend.toLowerCase()}
          valueClassName={trendColor(asset.trend)}
        />
        <MetricRow label="Momentum" value={`${asset.buyer_strength.toFixed(0)}%`} />
        <MetricRow label="Risk" value={`${asset.risk.toFixed(0)}%`} />
        <MetricRow label="EV" value={asset.expected_value.toFixed(2)} />
      </Link>
    </article>
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
