"use client";

import { useAnalysis } from "@/hooks/use-analysis";

interface AIExplanationCardProps {
  symbol: string;
}

export function AIExplanationCard({ symbol }: AIExplanationCardProps) {
  const { data, isLoading, error } = useAnalysis(symbol);

  if (isLoading) {
    return (
      <div className="surface p-5 lg:col-span-2">
        <div className="h-20 animate-pulse bg-muted/30" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface p-5 lg:col-span-2">
        <h2 className="label-caps">Analysis</h2>
        <p className="mt-3 text-sm text-muted-foreground">Unable to load.</p>
      </div>
    );
  }

  return (
    <div className="surface p-5 lg:col-span-2">
      <div className="flex items-baseline justify-between">
        <h2 className="label-caps">Analysis</h2>
        <span className="font-mono text-[10px] text-muted-foreground">
          {data.source === "groq" ? "groq" : "local"}
        </span>
      </div>

      <p className="mt-4 text-sm leading-relaxed text-foreground/90">{data.summary}</p>

      {data.factors.length > 0 && (
        <ul className="mt-5 space-y-2 border-t border-white/[0.06] pt-4">
          {data.factors.map((factor) => (
            <li key={factor} className="font-mono text-xs leading-relaxed text-muted-foreground">
              {factor}
            </li>
          ))}
        </ul>
      )}

      {data.conflicts.length > 0 && (
        <div className="mt-4 border-t border-white/[0.06] pt-4">
          <p className="label-caps">Conflicts</p>
          <ul className="mt-2 space-y-1.5">
            {data.conflicts.map((conflict) => (
              <li key={conflict} className="text-xs text-neutral">
                {conflict}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
