import Link from "next/link";

import type { DashboardDensity } from "@/hooks/use-dashboard-view";
import { cn } from "@/lib/utils";
import type { AssetQuote, AssetSummary } from "@/services/api";

interface AssetCardProps {
  asset: AssetSummary;
  quote?: AssetQuote | null;
  density?: DashboardDensity;
  rank?: number;
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

function gradeClass(grade: string): string {
  if (grade === "A+" || grade === "A") return "text-foreground";
  if (grade === "B") return "text-foreground/75";
  return "text-muted-foreground";
}

export function AssetCard({ asset, quote, density = "m", rank }: AssetCardProps) {
  const change = quote?.change_pct;
  const compact = density === "s";
  const changeClass =
    change == null
      ? "text-muted-foreground"
      : change > 0
        ? "text-bullish"
        : change < 0
          ? "text-bearish"
          : "text-neutral";

  return (
    <article
      className={cn(
        "surface-interactive group",
        compact ? "p-3" : "p-5",
      )}
    >
      <div
        className={cn(
          "flex items-start justify-between gap-3 border-b border-white/[0.06]",
          compact ? "pb-3" : "pb-4",
        )}
      >
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <Link
              href={`/assets/${asset.symbol}`}
              className={cn(
                "font-mono tracking-wide text-foreground transition-colors hover:text-foreground/90",
                compact ? "text-sm" : "text-lg",
              )}
            >
              {asset.symbol}
            </Link>
            <span className="label-caps !normal-case tracking-wide text-muted-foreground/70">
              {asset.asset_class}
            </span>
          </div>
          <Link href={`/assets/${asset.symbol}`} className="mt-1 block">
            <p className="font-mono text-[11px] text-muted-foreground transition-colors group-hover:text-foreground/75">
              {stateLabel(asset.trade_state)} · {asset.execution_signal.toLowerCase()}
            </p>
            {quote?.available && quote.price != null ? (
              <p className={cn("mt-2 flex items-baseline gap-2 font-mono", compact ? "text-xs" : "text-sm")}>
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
        <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
          {rank != null ? (
            <span
              className={cn(
                "text-sm leading-none",
                rank <= 3 ? "rank-num" : "rank-num-muted",
              )}
            >
              #{rank}
            </span>
          ) : null}
          <Link
            href={`/assets/${asset.symbol}`}
            className={cn(
              "font-mono leading-none transition-colors hover:text-foreground",
              compact ? "text-xs" : "text-sm",
              gradeClass(asset.trade_grade),
            )}
          >
            {asset.trade_grade}
          </Link>
        </div>
      </div>

      <Link
        href={`/assets/${asset.symbol}`}
        className={cn("block space-y-2.5", compact ? "mt-3" : "mt-4")}
      >
        <MetricRow label="Confidence" value={`${asset.confidence.toFixed(0)}%`} compact={compact} />
        <MetricRow
          label="Trend"
          value={asset.trend.toLowerCase()}
          valueClassName={trendColor(asset.trend)}
          compact={compact}
        />
        {!compact ? (
          <MetricRow label="EV" value={asset.expected_value.toFixed(2)} />
        ) : null}
      </Link>
    </article>
  );
}

function MetricRow({
  label,
  value,
  valueClassName,
  compact,
}: {
  label: string;
  value: string;
  valueClassName?: string;
  compact?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between text-sm">
      <span className="label-caps">{label}</span>
      <span
        className={cn(
          "font-mono",
          compact ? "text-xs" : "text-[13px]",
          valueClassName ?? "text-foreground/90",
        )}
      >
        {value}
      </span>
    </div>
  );
}
