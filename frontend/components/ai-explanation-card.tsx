"use client";

import { useAnalysis } from "@/hooks/use-analysis";
import type { AIExplanation, AIExplanationVariant } from "@/services/api";

interface AIExplanationCardProps {
  symbol: string;
}

function sourceLabel(source: string): string {
  if (source === "groq") return "groq";
  return "local desk";
}

function VariantBody({
  title,
  data,
  hint,
}: {
  title: string;
  data: AIExplanationVariant | AIExplanation;
  hint?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="label-caps">{title}</h3>
        <span className="font-mono text-[10px] text-muted-foreground">
          {sourceLabel(data.source)}
        </span>
      </div>
      {hint ? <p className="mt-2 text-xs text-muted-foreground">{hint}</p> : null}
      <p className="mt-3 text-sm leading-relaxed text-foreground/90">{data.summary}</p>
      {data.factors.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-white/[0.06] pt-3">
          {data.factors.map((factor) => (
            <li key={factor} className="font-mono text-xs leading-relaxed text-muted-foreground">
              {factor}
            </li>
          ))}
        </ul>
      )}
      {data.conflicts.length > 0 && (
        <div className="mt-3 border-t border-white/[0.06] pt-3">
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

export function AIExplanationCard({ symbol }: AIExplanationCardProps) {
  const { data, isLoading, error } = useAnalysis(symbol, true);

  if (isLoading) {
    return (
      <div className="surface p-5 sm:col-span-2 lg:col-span-3">
        <p className="label-caps">Analysis</p>
        <p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/60">
          Comparing Groq and desk reasoning…
        </p>
        <div className="mt-4 h-24 animate-pulse bg-muted/30" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface p-5 sm:col-span-2 lg:col-span-3">
        <h2 className="label-caps">Analysis</h2>
        <p className="mt-3 text-sm text-muted-foreground">Unable to load.</p>
      </div>
    );
  }

  const local = data.local;
  const groq = data.groq;
  const showCompare = local != null;

  if (showCompare) {
    const groqHint =
      data.groq_status === "unavailable"
        ? "Set GROQ_API_KEY on the API to add a Groq reading beside the desk synthesizer."
        : data.groq_status === "failed"
          ? "Groq failed this pass — desk reasoning is still below."
          : undefined;
    return (
      <div className="surface p-5 sm:col-span-2 lg:col-span-3">
        <h2 className="label-caps">Analysis</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Same evidence, two write-ups — desk synthesizer vs Groq. Neither is an order.
        </p>
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <VariantBody title="Desk" data={local} />
          {groq ? (
            <VariantBody title="Groq" data={groq} />
          ) : (
            <div>
              <h3 className="label-caps">Groq</h3>
              <p className="mt-3 text-sm text-muted-foreground">{groqHint}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="surface p-5 sm:col-span-2 lg:col-span-3">
      <VariantBody title="Analysis" data={data} />
    </div>
  );
}
