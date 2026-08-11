"use client";

import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { useAssets } from "@/hooks/use-assets";
import { type AlertStatus, fetchAlertStatus } from "@/services/api";
import { cn } from "@/lib/utils";

export function DashboardHeader() {
  const [alerts, setAlerts] = useState<AlertStatus | null>(null);
  const { data } = useAssets();
  const assets = data?.assets;
  const rankingStatus = data?.ranking_status;

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

  const marketDegraded = assets?.some((asset) => asset.data_degraded) === true;
  const rankingWarming = rankingStatus === "warming" || rankingStatus === "stale";
  const statusTone = marketDegraded ? "degraded" : rankingWarming ? "warming" : "live";
  const statusLabel =
    statusTone === "degraded" ? "degraded" : statusTone === "warming" ? "warming" : "live";

  return (
    <SiteHeader
      trailing={
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "idle-dot",
              statusTone === "degraded" && "idle-dot-degraded",
              statusTone === "warming" && "idle-dot-warming",
            )}
          />
          <span
            className={cn(
              "font-mono text-[11px] uppercase tracking-widest",
              statusTone === "degraded"
                ? "text-amber-200/90"
                : statusTone === "warming"
                  ? "text-muted-foreground"
                  : "text-muted-foreground",
            )}
          >
            {statusLabel}
          </span>
        </div>
      }
      subtitle={
        alertLabel ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/80">
            {alertLabel}
            {alerts?.discord_configured ? ` · discord ${alerts.discord_mode}` : ""}
            {alerts?.email_configured ? " · email" : ""}
            {marketDegraded ? " · market data stale" : ""}
            {rankingWarming && !marketDegraded ? " · ranks updating" : ""}
          </p>
        ) : marketDegraded ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-amber-200/70">
            market data stale
          </p>
        ) : rankingWarming ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
            ranks updating
          </p>
        ) : null
      }
    />
  );
}
