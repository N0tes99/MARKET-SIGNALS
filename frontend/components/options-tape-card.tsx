"use client";

import Link from "next/link";

import { TRACKED_SYMBOLS } from "@/config/assets";
import { cn } from "@/lib/utils";
import type { TapeHunt } from "@/services/api";

const TRACKED = new Set<string>(TRACKED_SYMBOLS);

function Meta({
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
      <p className="label-caps text-muted-foreground/45">{label}</p>
      <p className={cn("font-mono text-xs", className)}>{value}</p>
    </div>
  );
}

export function OptionsTapeCard({ hunt }: { hunt: TapeHunt }) {
  const opt = hunt.selected_option;
  const plan = hunt.execution_plan;
  const tracked = TRACKED.has(hunt.symbol);
  const bull = hunt.direction === "long";

  return (
    <article className="surface p-4 sm:p-5">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <Link
              href={tracked ? `/assets/${hunt.symbol}` : `/radar/${hunt.symbol}`}
              className="font-mono text-sm tracking-wide underline-offset-2 hover:underline"
            >
              {hunt.symbol}
            </Link>
            <span
              className={cn(
                "font-mono text-[10px] uppercase tracking-widest",
                bull ? "text-bullish" : "text-bearish",
              )}
            >
              {hunt.direction} {opt?.right ?? ""}
            </span>
            {hunt.heat === "hot" ? (
              <span className="font-mono text-[10px] uppercase tracking-widest text-amber-200/80">
                hot
              </span>
            ) : null}
            {!tracked ? (
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/45">
                radar
              </span>
            ) : null}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <span className={cn("font-mono text-sm", bull ? "text-bullish" : "text-bearish")}>
            {hunt.hunt_score.toFixed(0)}
          </span>
          <p className="font-mono text-[10px] text-muted-foreground/50">hunt</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
        <Meta
          label="Rel vol"
          value={`${hunt.relative_volume.toFixed(1)}×`}
          className={hunt.relative_volume >= 2 ? "text-amber-100/90" : undefined}
        />
        <Meta label="5D" value={`${hunt.ret_5d_pct >= 0 ? "+" : ""}${hunt.ret_5d_pct.toFixed(1)}%`} />
        <Meta label="20D" value={`${hunt.ret_20d_pct >= 0 ? "+" : ""}${hunt.ret_20d_pct.toFixed(1)}%`} />
        <Meta label="P/C" value={hunt.put_call_vol.toFixed(2)} />
        <Meta label="Opt vol" value={hunt.option_volume.toLocaleString()} />
        {hunt.unusual_vol_oi > 0 ? (
          <Meta label="Vol/OI" value={hunt.unusual_vol_oi.toFixed(1)} />
        ) : null}
      </div>

      {opt ? (
        <p className="mt-3 font-mono text-[11px] text-muted-foreground">
          {opt.right} {opt.strike} · {opt.expiry} · {opt.dte}d · vol {opt.volume ?? "—"}
        </p>
      ) : null}

      {plan?.invalidation[0] ? (
        <p className="mt-2 font-mono text-[10px] leading-relaxed text-muted-foreground/70">
          {plan.invalidation[0]}
          {plan.max_risk_usd != null ? ` · max ~$${plan.max_risk_usd.toFixed(0)}` : ""}
        </p>
      ) : null}

      {hunt.factors.slice(0, 2).map((factor) => (
        <p key={factor} className="mt-2 text-xs leading-relaxed text-muted-foreground/80">
          {factor}
        </p>
      ))}

      {hunt.conflicts[0] ? (
        <p className="mt-2 text-xs leading-relaxed text-amber-100/70">{hunt.conflicts[0]}</p>
      ) : null}
    </article>
  );
}
