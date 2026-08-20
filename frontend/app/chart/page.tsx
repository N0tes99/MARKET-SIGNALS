"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { ChartAnalyzerPanel } from "@/components/chart-analyzer-panel";
import { SiteHeader } from "@/components/site-header";
import { fetchHealth } from "@/services/api";

export default function ChartAnalyzerPage() {
  const { user } = useAuth();
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  useEffect(() => {
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
  }, []);

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
        {apiUp === false ? (
          <p className="mt-4 font-mono text-[11px] leading-relaxed text-muted-foreground">
            API is not running. In a second PowerShell window:
            <br />
            cd backend
            <br />
            py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
            <br />
            Then refresh this page.
          </p>
        ) : null}
        {apiUp === true && !user ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Local scans work without an account.{" "}
            <Link href="/login?next=/chart" className="underline-offset-4 hover:underline">
              Sign in
            </Link>{" "}
            if you want a saved session.
          </p>
        ) : null}
        <div className="mt-8">
          <ChartAnalyzerPanel />
        </div>
      </div>
    </main>
  );
}
