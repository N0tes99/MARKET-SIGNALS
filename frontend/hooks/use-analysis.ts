"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAnalysis } from "@/services/api";

export function useAnalysis(symbol: string, compare = false) {
  return useQuery({
    queryKey: ["analysis", symbol, compare],
    queryFn: () => fetchAnalysis(symbol, { compare }),
    staleTime: 300_000,
    refetchOnWindowFocus: false,
  });
}
