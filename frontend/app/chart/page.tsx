"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { ChartAnalyzerPanel } from "@/components/chart-analyzer-panel";
import { SiteHeader } from "@/components/site-header";
import { fetchHealth } from "@/services/api";

export default function ChartAnalyzerPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login?next=/chart");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void fetchHealth(3_000)
      .then(() => {
        if (!cancelled) setApiUp(true);
      })
      .catch(() => {
        if (!cancelled) setApiUp(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (loading || !user) {
    return (
      <main className="min-h-screen">
        <SiteHeader compact title="Chart analyst" />
        <p className="p-8 font-mono text-[11px] uppercase tracking-widest text-muted-foreground/50">
          Sign in to open Chart
        </p>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Chart analyst" />
      <div className="container mx-auto max-w-3xl px-4 py-10 sm:py-14">
        <p className="label-caps">Vision</p>
        <h1 className="mt-2 font-brand text-3xl font-medium tracking-tight">Chart screenshot</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Drop a trade screenshot. The analyst ranks the best long, best short,
          and a stand-aside. A Groq scan is often 15–45 seconds, not instant.
          Desk engines still decide — this does not place orders.
        </p>
        {apiUp === false ? (
          <div className="surface mt-6 px-4 py-3">
            <p className="font-mono text-[11px] uppercase tracking-widest text-neutral">
              API offline
            </p>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Start uvicorn on 127.0.0.1:8000 in the backend folder, then refresh.
            </p>
          </div>
        ) : null}
        <div className="mt-8">
          <ChartAnalyzerPanel />
        </div>
      </div>
    </main>
  );
}
