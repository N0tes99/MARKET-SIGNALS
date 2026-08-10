"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import type { OpportunityIdea, SetupType } from "@/services/api";

export const SETUP_LABEL: Record<SetupType, string> = {
  funding_extreme: "Funding extreme",
  liq_flush: "Liq flush",
  basis_rich: "Basis rich",
};

function confidenceColor(score: number): string {
  if (score >= 60) return "text-bullish";
  if (score <= 40) return "text-bearish";
  return "text-neutral";
}

function directionColor(direction: string): string {
  if (direction === "long") return "text-bullish";
  if (direction === "short") return "text-bearish";
  return "text-muted-foreground";
}

export function formatSetupUpdated(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

interface SetupIdeaCardProps {
  idea: OpportunityIdea;
  /** Show symbol + link to asset detail (dashboard feed). */
  showSymbol?: boolean;
}

export function SetupIdeaCard({ idea, showSymbol = false }: SetupIdeaCardProps) {
  const factors = idea.factors.slice(0, 3);
  const title = SETUP_LABEL[idea.setup_type];

  return (
    <article className="surface p-5">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          {showSymbol ? (
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <Link
                href={`/assets/${idea.symbol}`}
                className="font-mono text-sm tracking-wide text-foreground/90 underline-offset-2 hover:underline"
              >
                {idea.symbol}
              </Link>
              <h3 className="label-caps text-muted-foreground/70">{title}</h3>
            </div>
          ) : (
            <h3 className="label-caps">{title}</h3>
          )}
        </div>
        <span className={cn("shrink-0 font-mono text-sm", confidenceColor(idea.confidence))}>
          {idea.confidence.toFixed(0)}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
        <Meta
          label="Bias"
          value={idea.direction_bias}
          className={directionColor(idea.direction_bias)}
        />
        <Meta label="Hint" value={idea.trade_state_hint.toLowerCase()} />
        {idea.data_quality !== "good" && (
          <Meta label="Data" value={idea.data_quality} className="text-neutral" />
        )}
      </div>

      {factors.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3">
          {factors.map((factor) => (
            <li key={factor} className="font-mono text-[11px] leading-relaxed text-muted-foreground">
              {factor}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 font-mono text-[10px] text-muted-foreground/55">
        updated {formatSetupUpdated(idea.as_of)}
      </p>
    </article>
  );
}

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
      <p className="label-caps text-muted-foreground/55">{label}</p>
      <p className={cn("mt-0.5 font-mono text-xs", className ?? "text-foreground/85")}>{value}</p>
    </div>
  );
}
