"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAssets } from "@/services/api";

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

export function useAssets() {
  return useQuery({
    queryKey: ["assets"],
    queryFn: fetchAssets,
    staleTime: 120_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
    // Gateway failures are expected until keep-warm fills the disk/memory cache.
    // Poll every 20s so rankings appear without a manual refresh.
    retry: (failureCount, error) => {
      if (isGatewayTimeout(error)) return failureCount < 2;
      return failureCount < 1;
    },
    retryDelay: (attempt) => Math.min(5_000 * (attempt + 1), 20_000),
    refetchInterval: (query) => (query.state.error ? 20_000 : false),
    placeholderData: (previous) => previous,
  });
}
