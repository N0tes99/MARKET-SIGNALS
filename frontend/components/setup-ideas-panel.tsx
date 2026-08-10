"use client";

import { SetupIdeaCard } from "@/components/setup-idea-card";
import { useSetups } from "@/hooks/use-setups";

interface SetupIdeasPanelProps {
  symbol: string;
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
          <SetupIdeaCard key={idea.id} idea={idea} />
        ))}
      </div>
    </section>
  );
}
