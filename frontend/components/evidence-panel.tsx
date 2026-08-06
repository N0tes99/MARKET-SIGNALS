"use client";

import { useState } from "react";

import { useEvidence } from "@/hooks/use-evidence";
import { AIExplanationCard } from "@/components/ai-explanation-card";
import { BacktestPanel } from "@/components/backtest-panel";
import { SimilarityPanel } from "@/components/similarity-panel";
import { WeightTuningPanel } from "@/components/weight-tuning-panel";
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
      <div className="mt-10 space-y-3">
        <div className="surface h-24 animate-pulse" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="surface h-32 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface mt-10 p-8 text-center">
        <p className="text-sm text-muted-foreground">
          Unable to load evidence. Start the backend to see live data.
        </p>
      </div>
    );
  }

  const itemsByCategory = Object.fromEntries(data.items.map((item) => [item.category, item]));

  return (
    <div className="mt-10 space-y-3">
      <div className="surface p-6">
        <div className="flex items-end justify-between">
          <div>
            <p className="label-caps">Confidence</p>
            <p className="mt-2 font-mono text-4xl font-light tracking-tight">
              {data.total_confidence.toFixed(1)}
              <span className="ml-1 text-lg text-muted-foreground">%</span>
            </p>
          </div>
          <div className="text-right">
            <p className="label-caps">Timeframe</p>
            <p className="mt-2 font-mono text-sm">{data.timeframe}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(SECTION_MAP).map(([section, categories]) => {
          const item = categories.map((c) => itemsByCategory[c]).find(Boolean);
          return (
            <div key={section} className="surface p-5">
              <div className="flex items-baseline justify-between">
                <h2 className="label-caps">{section}</h2>
                {item && (
                  <span className={cn("font-mono text-sm", scoreColor(item.score))}>
                    {item.score.toFixed(0)}
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {item?.description ?? "—"}
              </p>
              {item && (
                <p className="mt-3 font-mono text-[10px] text-muted-foreground/70">
                  w{item.weight} · {item.source}
                </p>
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
              AI analysis, similar setups, backtests, and weight tuning are deferred so the page
              loads faster.
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
