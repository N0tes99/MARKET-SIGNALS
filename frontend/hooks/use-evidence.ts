"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchEvidence } from "@/services/api";

export function useEvidence(symbol: string) {
  return useQuery({
    queryKey: ["evidence", symbol],
    queryFn: () => fetchEvidence(symbol),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}
