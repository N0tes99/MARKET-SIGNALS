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
    // Cold rank_all already takes ~1 min; stacking 2× backoff on 504 adds minutes.
    // Fail fast on gateway timeouts; at most one retry for transient errors.
    retry: (failureCount, error) => {
      if (isGatewayTimeout(error)) return false;
      return failureCount < 1;
    },
    retryDelay: 3_000,
    placeholderData: (previous) => previous,
  });
}
