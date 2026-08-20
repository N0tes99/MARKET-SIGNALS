"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ExpansionRow = {
  symbol: string;
  state: string;
  compression: { score: number };
  squeeze: { score: number };
  trigger: { active: boolean; volume_ratio?: number | null };
  net_score: number;
};

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

  const stateColor = (s: string) => {
    switch (s?.toLowerCase()) {
      case "primed":
        return "bg-amber-500/20 text-amber-400";
      case "triggering":
        return "bg-orange-500/20 text-orange-400";
      case "expanding":
        return "bg-green-500/20 text-green-400";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Expansion Radar</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Surface 5 — compression, squeeze fuel, breakout trigger (BTC / SOL / SUI)
        </p>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {rows.map((r) => (
            <Card key={r.symbol}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between text-lg">
                  {r.symbol}
                  <Badge className={stateColor(r.state)}>{r.state}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Compression</span>
                  <span>{r.compression.score.toFixed(0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Squeeze fuel</span>
                  <span>{r.squeeze.score.toFixed(0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Net score</span>
                  <span>{r.net_score.toFixed(0)}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
