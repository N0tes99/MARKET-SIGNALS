"use client";

import { useSetups } from "@/hooks/use-setups";
import { cn } from "@/lib/utils";
import type { OpportunityIdea, SetupType } from "@/services/api";

interface SetupIdeasPanelProps {
  symbol: string;
}

const SETUP_LABEL: Record<SetupType, string> = {
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

function formatUpdated(iso: string): string {
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

export function SetupIdeasPanel({ symbol }: SetupIdeasPanelProps) {
  const { data, isLoading, error } = useSetups(symbol);

  if (isLoading) {
    return <div className="surface skeleton h-20" />;
  }

  if (error) {
    return null;
  }

  const setups = data?.setups ?? [];
  if (setups.length === 0) {
    return (
      <section className="motion-fade-in border-b border-white/[0.04] py-2">
        <p className="label-caps text-muted-foreground/45">Setup ideas</p>
        <p className="mt-2 text-sm text-muted-foreground/50">No active setups.</p>
      </section>
    );
  }

  return (
    <section className="motion-fade-in space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="label-caps">Setup ideas</p>
        <p className="font-mono text-[10px] text-muted-foreground/50">watch candidates</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {setups.map((idea) => (
          <SetupCard key={idea.id} idea={idea} />
        ))}
      </div>
    </section>
  );
}

function SetupCard({ idea }: { idea: OpportunityIdea }) {
  const factors = idea.factors.slice(0, 3);

  return (
    <article className="surface p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="label-caps">{SETUP_LABEL[idea.setup_type]}</h3>
        <span className={cn("font-mono text-sm", confidenceColor(idea.confidence))}>
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
        updated {formatUpdated(idea.as_of)}
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
