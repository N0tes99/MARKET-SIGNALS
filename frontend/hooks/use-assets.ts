"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  dashboardStreamUrl,
  fetchAssets,
  type AssetsDashboard,
} from "@/services/api";

function isGatewayTimeout(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    msg.includes("504") ||
    msg.includes("502") ||
    msg.includes("timed out") ||
    msg.includes("timeout")
  );
}

function isTabVisible(): boolean {
  if (typeof document === "undefined") return true;
  return document.visibilityState === "visible";
}

export function useAssets() {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }
    let source: EventSource | null = null;
    try {
      source = new EventSource(dashboardStreamUrl());
    } catch {
      return;
    }
    const onDashboard = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as AssetsDashboard;
        if (!payload || !Array.isArray(payload.assets)) return;
        queryClient.setQueryData(["assets"], payload);
      } catch {
        /* ignore malformed chunks */
      }
    };
    source.addEventListener("dashboard", onDashboard);
    source.onmessage = onDashboard;
    return () => {
      source?.removeEventListener("dashboard", onDashboard);
      source?.close();
    };
  }, [queryClient]);

  return useQuery({
    queryKey: ["assets"],
    queryFn: fetchAssets,
    staleTime: 60_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
    retry: (failureCount, error) => {
      if (isGatewayTimeout(error)) return failureCount < 2;
      return failureCount < 1;
    },
    retryDelay: (attempt) => Math.min(5_000 * (attempt + 1), 20_000),
    // Poll while ranking is warming/stale, or after errors — only when tab is visible.
    refetchInterval: (query) => {
      if (!isTabVisible()) return false;
      if (query.state.error) return 15_000;
      const data = query.state.data as AssetsDashboard | undefined;
      if (!data) return false;
      if (data.ranking_status === "warming") return 8_000;
      if (data.ranking_status === "stale") return 20_000;
      return 90_000;
    },
    placeholderData: (previous) => previous,
  });
}
