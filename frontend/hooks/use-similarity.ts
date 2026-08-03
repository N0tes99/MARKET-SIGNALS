"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchSimilarity } from "@/services/api";

export function useSimilarity(symbol: string) {
  return useQuery({
    queryKey: ["similarity", symbol],
    queryFn: () => fetchSimilarity(symbol),
    staleTime: 60_000,
  });
}
