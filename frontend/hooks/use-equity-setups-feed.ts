"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchEquitySetupsFeed } from "@/services/api";

export function useEquitySetupsFeed(opts?: {
  watchOnly?: boolean;
  minConfidence?: number;
}) {
  const watchOnly = opts?.watchOnly ?? true;
  const minConfidence = opts?.minConfidence ?? 55;

  return useQuery({
    queryKey: ["equity-setups-feed", watchOnly, minConfidence],
    queryFn: () => fetchEquitySetupsFeed({ watchOnly, minConfidence }),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}
