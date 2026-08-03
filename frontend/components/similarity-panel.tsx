"use client";

import { useSimilarity } from "@/hooks/use-similarity";

interface SimilarityPanelProps {
  symbol: string;
}

export function SimilarityPanel({ symbol }: SimilarityPanelProps) {
  const { data, isLoading, error } = useSimilarity(symbol);

  if (isLoading) {
    return (
      <div className="surface bg-card p-5">
        <div className="h-16 animate-pulse bg-muted/30" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface bg-card p-5">
        <h2 className="label-caps">Similarity</h2>
        <p className="mt-3 text-sm text-muted-foreground">Unable to load.</p>
      </div>
    );
  }

  return (
    <div className="surface bg-card p-5">
      <div className="flex items-baseline justify-between">
        <h2 className="label-caps">Similarity</h2>
        <span className="font-mono text-[10px] text-muted-foreground">
          {data.history_count} in memory
        </span>
      </div>

      {data.matches.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Building history — refresh a few times to find matches.
        </p>
      ) : (
        <ul className="mt-4 space-y-3 border-t border-border pt-4">
          {data.matches.map((match) => (
            <li key={match.id} className="flex items-baseline justify-between gap-4">
              <div>
                <p className="font-mono text-xs text-foreground/90">
                  {match.trade_grade} · {match.trade_state.toLowerCase()}
                </p>
                <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                  {new Date(match.timestamp).toLocaleString()}
                </p>
              </div>
              <div className="text-right">
                <p className="font-mono text-sm">{match.similarity.toFixed(0)}%</p>
                <p className="font-mono text-[10px] text-muted-foreground">match</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
