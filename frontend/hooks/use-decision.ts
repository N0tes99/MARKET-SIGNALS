"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchDecision } from "@/services/api";

export function useDecision(symbol: string) {
  return useQuery({
    queryKey: ["decision", symbol],
    queryFn: () => fetchDecision(symbol),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}
