"use client";

import { useEffect, useState } from "react";

import { type AlertStatus, fetchAlertStatus } from "@/services/api";

export function DashboardHeader() {
  const [alerts, setAlerts] = useState<AlertStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAlertStatus()
      .then((status) => {
        if (!cancelled) setAlerts(status);
      })
      .catch(() => {
        if (!cancelled) setAlerts(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const alertLabel = alerts
    ? alerts.enabled
      ? `alerts ${alerts.min_grade}+/${alerts.min_confidence}%`
      : "alerts off"
    : null;

  return (
    <header className="border-b border-white/[0.06] bg-card/25 backdrop-blur-xl">
      <div className="container mx-auto flex items-end justify-between px-4 py-8">
        <div>
          <p className="label-caps mb-3">Signal Engine</p>
          <h1 className="text-2xl font-light tracking-tight text-foreground">
            Market intelligence
          </h1>
        </div>
        <div className="flex flex-col items-end gap-2 pb-1">
          <div className="flex items-center gap-2">
            <span className="idle-dot" />
            <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              live
            </span>
          </div>
          {alertLabel ? (
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/80">
              {alertLabel}
              {alerts?.discord_configured ? ` · discord ${alerts.discord_mode}` : ""}
              {alerts?.email_configured ? " · email" : ""}
            </p>
          ) : null}
        </div>
      </div>
    </header>
  );
}
