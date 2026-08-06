"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAnalysis } from "@/services/api";

export function useAnalysis(symbol: string) {
  return useQuery({
    queryKey: ["analysis", symbol],
    queryFn: () => fetchAnalysis(symbol),
    staleTime: 300_000,
    refetchOnWindowFocus: false,
  });
}
