"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchSetupsFeed } from "@/services/api";

export function useSetupsFeed(opts?: { watchOnly?: boolean; minConfidence?: number }) {
  const watchOnly = opts?.watchOnly ?? true;
  const minConfidence = opts?.minConfidence ?? 55;

  return useQuery({
    queryKey: ["setups-feed", watchOnly, minConfidence],
    queryFn: () => fetchSetupsFeed({ watchOnly, minConfidence }),
    staleTime: 90_000,
    refetchOnWindowFocus: false,
    retry: 1,
    retryDelay: 4_000,
  });
}
