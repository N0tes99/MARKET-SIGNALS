"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import type { EquityOptionsIdea, EquitySetupType } from "@/services/api";
import { formatSetupUpdated } from "@/components/setup-idea-card";

const SETUP_LABEL: Record<EquitySetupType, string> = {
  momentum_continuation: "Momentum continuation",
  breakout_convexity: "Breakout convexity",
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

interface EquitySetupCardProps {
  idea: EquityOptionsIdea;
  showSymbol?: boolean;
  showPlan?: boolean;
}

export function EquitySetupCard({
  idea,
  showSymbol = false,
  showPlan = true,
}: EquitySetupCardProps) {
  const title = SETUP_LABEL[idea.setup_type];
  const opt = idea.selected_option;
  const plan = idea.execution_plan;
  const factors = idea.factors.slice(0, 3);

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
        <div className="shrink-0 text-right">
          <span className={cn("font-mono text-sm", confidenceColor(idea.opportunity_score))}>
            {idea.opportunity_score.toFixed(0)}
          </span>
          <p className="font-mono text-[10px] text-muted-foreground/50">opp</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
        <Meta
          label="Bias"
          value={idea.direction_bias}
          className={directionColor(idea.direction_bias)}
        />
        <Meta label="Hint" value={idea.trade_state_hint.toLowerCase()} />
        <Meta label="Mom" value={idea.momentum_score.toFixed(0)} />
        {idea.data_quality !== "good" && (
          <Meta label="Data" value={idea.data_quality} className="text-neutral" />
        )}
      </div>

      {opt ? (
        <div className="mt-4 border-t border-white/[0.06] pt-3">
          <p className="label-caps text-muted-foreground/55">Preferred option</p>
          <p className="mt-1 font-mono text-xs text-foreground/85">
            {opt.expiry} ${opt.strike.toFixed(0)} {opt.right}
            {opt.mid != null ? ` · mid $${opt.mid.toFixed(2)}` : ""}
            {` · score ${opt.overall_score.toFixed(0)}`}
          </p>
          {opt.rationale ? (
            <p className="mt-1 font-mono text-[11px] text-muted-foreground/70">{opt.rationale}</p>
          ) : null}
        </div>
      ) : null}

      {factors.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {factors.map((factor) => (
            <li key={factor} className="font-mono text-[11px] leading-relaxed text-muted-foreground">
              {factor}
            </li>
          ))}
        </ul>
      ) : null}

      {showPlan && plan ? (
        <div className="mt-4 space-y-3 border-t border-white/[0.06] pt-3">
          <div>
            <p className="label-caps text-muted-foreground/55">Execution plan</p>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground/80">{plan.setup_name}</p>
          </div>

          <div>
            <p className="label-caps text-muted-foreground/45">Entries</p>
            <ul className="mt-1.5 space-y-1.5">
              {plan.entries.map((entry) => (
                <li key={entry.step} className="font-mono text-[11px] text-muted-foreground">
                  <span className="text-foreground/70">
                    E{entry.step} {entry.label} {entry.size_pct.toFixed(0)}%
                  </span>
                  {entry.price_trigger != null ? ` @ $${entry.price_trigger.toFixed(2)}` : ""}
                  {" — "}
                  {entry.condition}
                </li>
              ))}
            </ul>
          </div>

          {plan.invalidation.length > 0 ? (
            <div>
              <p className="label-caps text-muted-foreground/45">Invalidation</p>
              <ul className="mt-1.5 space-y-1">
                {plan.invalidation.map((rule) => (
                  <li
                    key={rule}
                    className={cn(
                      "font-mono text-[10px] leading-relaxed",
                      rule.startsWith("HARD") ? "text-bearish/85" : "text-muted-foreground/70",
                    )}
                  >
                    {rule}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {plan.profit_zones.length > 0 ? (
            <div>
              <p className="label-caps text-muted-foreground/45">Harvest</p>
              <ul className="mt-1.5 space-y-1">
                {plan.profit_zones.map((zone) => (
                  <li
                    key={`${zone.option_gain_pct}-${zone.take_pct}`}
                    className="font-mono text-[10px] text-muted-foreground/75"
                  >
                    {zone.label}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <p className="label-caps text-muted-foreground/45">Runner</p>
            <p className="mt-1 font-mono text-[10px] leading-relaxed text-muted-foreground/75">
              {plan.runner_rule ||
                `Leave ~${plan.runner_pct.toFixed(0)}% after harvest targets.`}
            </p>
            {plan.max_risk_usd != null ? (
              <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
                Suggested max risk ~${plan.max_risk_usd.toFixed(0)}
              </p>
            ) : null}
          </div>

          {plan.notes ? (
            <p className="font-mono text-[10px] leading-relaxed text-muted-foreground/50">
              {plan.notes}
            </p>
          ) : null}
        </div>
      ) : null}

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
