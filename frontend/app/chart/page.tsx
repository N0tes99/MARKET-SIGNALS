"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { ChartAnalyzerPanel } from "@/components/chart-analyzer-panel";
import { SiteHeader } from "@/components/site-header";

export default function ChartAnalyzerPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login?next=/chart");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="min-h-screen">
        <SiteHeader compact />
        <p className="p-8 font-mono text-[11px] text-muted-foreground/50">
          Waiting for API on 127.0.0.1:8000…
        </p>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Chart analyst" />
      <div className="container mx-auto max-w-3xl px-4 py-10">
        <p className="label-caps">Vision</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Chart screenshot</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Drop a screenshot and the local Qwen scan ranks the best setups
          automatically. Gemini is not required.
        </p>
        <div className="mt-8">
          <ChartAnalyzerPanel />
        </div>
      </div>
    </main>
  );
}
