"use client";

import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
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
    <SiteHeader
      trailing={
        <div className="flex items-center gap-2">
          <span className="idle-dot" />
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
            live
          </span>
        </div>
      }
      subtitle={
        alertLabel ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/80">
            {alertLabel}
            {alerts?.discord_configured ? ` · discord ${alerts.discord_mode}` : ""}
            {alerts?.email_configured ? " · email" : ""}
          </p>
        ) : null
      }
    />
  );
}
