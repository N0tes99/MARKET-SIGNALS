"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAssets } from "@/services/api";

export function useAssets() {
  return useQuery({
    queryKey: ["assets"],
    queryFn: fetchAssets,
    staleTime: 120_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
    retry: 2,
    retryDelay: (attempt) => Math.min(5_000 * 2 ** attempt, 20_000),
    placeholderData: (previous) => previous,
  });
}
