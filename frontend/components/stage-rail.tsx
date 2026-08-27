"use client";

import type { RunnerStage } from "@/services/api";

export const RUNNER_STAGES: { key: RunnerStage; n: number; short: string }[] = [
  { key: "dormant", n: 0, short: "Dorm" },
  { key: "fundamental_inflection", n: 1, short: "Infl" },
  { key: "early_accumulation", n: 2, short: "Acc" },
  { key: "catalyst", n: 3, short: "Cat" },
  { key: "ignition", n: 4, short: "Ign" },
  { key: "discovery", n: 5, short: "Disc" },
  { key: "momentum", n: 6, short: "Mom" },
  { key: "extended", n: 7, short: "Ext" },
];

export function StageRail({
  stage,
  compact = false,
}: {
  stage: RunnerStage;
  compact?: boolean;
}) {
  const current = RUNNER_STAGES.findIndex((s) => s.key === stage);

  if (compact) {
    return (
      <ol className="flex items-center gap-0.5" aria-label={`stage ${stage.replaceAll("_", " ")}`}>
        {RUNNER_STAGES.map((s, i) => {
          const reached = current >= 0 && i <= current;
          const active = i === current;
          return (
            <li
              key={s.key}
              title={`${s.n} ${s.short}`}
              className={`h-1.5 w-1.5 rounded-full ${
                active
                  ? "bg-foreground"
                  : reached
                    ? "bg-muted-foreground/70"
                    : "bg-white/[0.12]"
              }`}
            />
          );
        })}
      </ol>
    );
  }

  return (
    <ol className="flex flex-wrap items-end gap-1" aria-label={`stage ${stage.replaceAll("_", " ")}`}>
      {RUNNER_STAGES.map((s, i) => {
        const reached = current >= 0 && i <= current;
        const active = i === current;
        return (
          <li
            key={s.key}
            className={`min-w-[2.25rem] border-b px-0.5 pb-1 text-center ${
              active
                ? "border-foreground text-foreground"
                : reached
                  ? "border-muted-foreground/40 text-muted-foreground"
                  : "border-white/[0.08] text-muted-foreground/30"
            }`}
          >
            <span className="block font-mono text-[9px] uppercase tracking-widest">{s.n}</span>
            <span className="block font-mono text-[9px] uppercase tracking-widest">{s.short}</span>
          </li>
        );
      })}
    </ol>
  );
}
