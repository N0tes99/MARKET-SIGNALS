"use client";

import { useState } from "react";

import { useEvidence } from "@/hooks/use-evidence";
import { AIExplanationCard } from "@/components/ai-explanation-card";
import { BacktestPanel } from "@/components/backtest-panel";
import { SimilarityPanel } from "@/components/similarity-panel";
import { WeightTuningPanel } from "@/components/weight-tuning-panel";
import { coinglassLiquidationsUrl } from "@/config/assets";
import { cn } from "@/lib/utils";

interface EvidencePanelProps {
  symbol: string;
}

const SECTION_MAP: Record<string, string[]> = {
  Trend: ["Trend"],
  Momentum: ["Momentum"],
  Volume: ["Volume"],
  "Market Structure": ["Structure"],
  Derivatives: ["Derivatives"],
  Macro: ["Macro"],
  Risk: ["Risk"],
  Correlation: ["Correlation"],
  Volatility: ["Volatility"],
  Events: ["Events"],
  "Sector RS": ["Sector RS"],
  "On-Chain": ["On-Chain"],
  Sentiment: ["Sentiment"],
};

function scoreColor(score: number): string {
  if (score >= 60) return "text-bullish";
  if (score <= 40) return "text-bearish";
  return "text-neutral";
}

export function EvidencePanel({ symbol }: EvidencePanelProps) {
  const { data, isLoading, error } = useEvidence(symbol);
  const [loadDeep, setLoadDeep] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="surface skeleton h-24" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="surface skeleton h-32" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface p-8 text-center">
        <p className="text-sm text-muted-foreground">
          Unable to load evidence. Retry in a moment — the API may still be warming.
        </p>
      </div>
    );
  }

  const itemsByCategory = Object.fromEntries(data.items.map((item) => [item.category, item]));
  const sentimentItems = data.items.filter((item) => item.category === "Sentiment");
  const liquidationsUrl = coinglassLiquidationsUrl(symbol);

  return (
    <div className="space-y-3">
      <div className="surface p-6">
        <div className="flex items-end justify-between">
          <div>
            <p className="label-caps">Evidence</p>
            <p className="mt-2 font-mono text-4xl font-light tracking-tight">
              {data.total_confidence.toFixed(1)}
              <span className="ml-1 text-lg text-muted-foreground">%</span>
            </p>
            <p className="mt-1 label-caps text-muted-foreground/60">total confidence</p>
          </div>
          <div className="text-right">
            <p className="label-caps">Timeframe</p>
            <p className="mt-2 font-mono text-sm">{data.timeframe}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(SECTION_MAP).map(([section, categories]) => {
          const sectionItems =
            section === "Sentiment"
              ? sentimentItems
              : categories.map((c) => itemsByCategory[c]).filter(Boolean);
          const item = sectionItems[0];
          const showLiquidations = section === "On-Chain" && liquidationsUrl;
          return (
            <div key={section} className="surface p-5">
              <div className="flex items-baseline justify-between gap-2">
                <div className="flex min-w-0 items-baseline gap-2">
                  <h2 className="label-caps">{section}</h2>
                  {showLiquidations && (
                    <a
                      href={liquidationsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-[10px] tracking-wide text-muted-foreground/45 underline-offset-2 transition-colors hover:text-muted-foreground hover:underline"
                    >
                      liquidations
                    </a>
                  )}
                </div>
                {item && (
                  <span className={cn("shrink-0 font-mono text-sm", scoreColor(item.score))}>
                    {item.score.toFixed(0)}
                  </span>
                )}
              </div>
              {sectionItems.length > 1 ? (
                <ul className="mt-3 space-y-2">
                  {sectionItems.map((row) => (
                    <li key={`${row.source}-${row.description.slice(0, 24)}`}>
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        {row.description}
                      </p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground/70">
                        <span className={scoreColor(row.score)}>{row.score.toFixed(0)}</span>
                        {" · "}w{row.weight} · {row.source}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {item?.description ?? "—"}
                  </p>
                  {item && (
                    <p className="mt-3 font-mono text-[10px] text-muted-foreground/70">
                      w{item.weight} · {item.source}
                    </p>
                  )}
                </>
              )}
            </div>
          );
        })}

        {loadDeep ? (
          <>
            <AIExplanationCard symbol={symbol} />
            <SimilarityPanel symbol={symbol} />
            <BacktestPanel symbol={symbol} />
            <WeightTuningPanel symbol={symbol} />
          </>
        ) : (
          <div className="surface flex flex-col justify-center p-5 sm:col-span-2 lg:col-span-3">
            <p className="text-sm text-muted-foreground">
              Groq vs desk reasoning, similar setups, backtests, and weight tuning are deferred so
              the page loads faster.
            </p>
            <button
              type="button"
              onClick={() => setLoadDeep(true)}
              className="mt-4 self-start border border-white/[0.12] px-3 py-2 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06]"
            >
              Load deeper analysis
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
