"use client";

import { EquitySetupCard } from "@/components/equity-setup-card";
import { useEquitySetups } from "@/hooks/use-equity-setups";

interface EquitySetupsPanelProps {
  symbol: string;
}

export function EquitySetupsPanel({ symbol }: EquitySetupsPanelProps) {
  const { data, isLoading, error } = useEquitySetups(symbol);

  if (isLoading) {
    return <div className="surface skeleton h-28" />;
  }

  if (error) {
    return null;
  }

  const setups = data?.setups ?? [];
  if (setups.length === 0) {
    return (
      <section className="motion-fade-in border-b border-white/[0.04] py-2">
        <p className="label-caps text-muted-foreground/45">Equity options plan</p>
        <p className="mt-2 text-sm text-muted-foreground/50">No Layer 3 setup active.</p>
      </section>
    );
  }

  return (
    <section className="motion-fade-in space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="label-caps">Equity options plan</p>
        <p className="font-mono text-[10px] text-muted-foreground/50">layer 3 · staged</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-1 lg:grid-cols-2">
        {setups.map((idea) => (
          <EquitySetupCard key={idea.id} idea={idea} showPlan />
        ))}
      </div>
    </section>
  );
}
