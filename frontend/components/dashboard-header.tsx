"use client";

import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { useAssets } from "@/hooks/use-assets";
import { type AlertStatus, fetchAlertStatus } from "@/services/api";
import { cn } from "@/lib/utils";

export function DashboardHeader() {
  const [alerts, setAlerts] = useState<AlertStatus | null>(null);
  const { data: assets } = useAssets();

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

  const degraded =
    assets?.some((asset) => asset.data_degraded) === true;

  return (
    <SiteHeader
      trailing={
        <div className="flex items-center gap-2">
          <span className={cn("idle-dot", degraded && "idle-dot-degraded")} />
          <span
            className={cn(
              "font-mono text-[11px] uppercase tracking-widest",
              degraded ? "text-amber-200/90" : "text-muted-foreground",
            )}
          >
            {degraded ? "degraded" : "live"}
          </span>
        </div>
      }
      subtitle={
        alertLabel ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/80">
            {alertLabel}
            {alerts?.discord_configured ? ` · discord ${alerts.discord_mode}` : ""}
            {alerts?.email_configured ? " · email" : ""}
            {degraded ? " · market data stale" : ""}
          </p>
        ) : degraded ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-amber-200/70">
            market data stale
          </p>
        ) : null
      }
    />
  );
}
