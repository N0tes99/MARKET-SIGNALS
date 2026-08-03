"use client";

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
  Funding: ["Derivatives"],
  Macro: ["Macro"],
  Risk: ["Risk"],
  Correlation: ["Correlation"],
  Volatility: ["Volatility"],
  Events: ["Events"],
};

function scoreColor(score: number): string {
  if (score >= 60) return "text-bullish";
  if (score <= 40) return "text-bearish";
  return "text-neutral";
}

export function EvidencePanel({ symbol }: EvidencePanelProps) {
  const { data, isLoading, error } = useEvidence(symbol);

  if (isLoading) {
    return (
      <div className="mt-10 space-y-px bg-border">
        <div className="surface h-24 animate-pulse bg-card" />
        <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="surface h-32 animate-pulse bg-card" />
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
    <div className="mt-10 space-y-px bg-border">
      <div className="surface bg-card p-6">
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

      <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(SECTION_MAP).map(([section, categories]) => {
          const item = categories.map((c) => itemsByCategory[c]).find(Boolean);
          return (
            <div key={section} className="surface bg-card p-5">
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

        <AIExplanationCard symbol={symbol} />

        <SimilarityPanel symbol={symbol} />

        <BacktestPanel symbol={symbol} />

        <WeightTuningPanel symbol={symbol} />
      </div>
    </div>
  );
}
