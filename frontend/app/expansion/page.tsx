"use client";

import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ExpansionRow = {
  symbol: string;
  state: string;
  compression: { score: number };
  squeeze: { score: number };
  trigger: { active: boolean; volume_ratio?: number | null };
  net_score: number;
};

function stateClass(state: string): string {
  switch (state?.toLowerCase()) {
    case "primed":
      return "text-amber-400";
    case "triggering":
      return "text-orange-400";
    case "expanding":
      return "text-bullish";
    default:
      return "text-muted-foreground";
  }
}

export default function ExpansionPage() {
  const [rows, setRows] = useState<ExpansionRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/v1/expansion`)
      .then((r) => r.json())
      .then((d) => setRows(d.candidates || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Expansion" />
      <div className="container mx-auto max-w-5xl space-y-6 px-4 py-8">
        <div>
          <p className="label-caps">Surface 5</p>
          <h1 className="mt-2 text-2xl font-light tracking-tight">Expansion radar</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Compression, squeeze fuel, breakout trigger (BTC / SOL / SUI)
          </p>
        </div>

        {loading ? (
          <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {rows.map((row) => (
              <article key={row.symbol} className="surface p-4">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="font-mono text-sm tracking-wide">{row.symbol}</h2>
                  <span className={cn("font-mono text-[10px] uppercase tracking-widest", stateClass(row.state))}>
                    {row.state}
                  </span>
                </div>
                <dl className="mt-3 space-y-1 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Compression</dt>
                    <dd>{row.compression?.score?.toFixed(0) ?? "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Squeeze fuel</dt>
                    <dd>{row.squeeze?.score?.toFixed(0) ?? "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Net score</dt>
                    <dd>{row.net_score?.toFixed(0) ?? "—"}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
