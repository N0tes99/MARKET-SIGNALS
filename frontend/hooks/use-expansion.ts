"use client";

import { useQuery } from "@tanstack/react-query";

import {
  fetchCortexHealth,
  fetchCortexMemory,
  fetchCortexSemantic,
  fetchExpansionFeed,
  fetchExpansionSymbol,
} from "@/services/api";

export function useExpansionFeed() {
  return useQuery({
    queryKey: ["expansion-feed"],
    queryFn: fetchExpansionFeed,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

export function useCortexMemory() {
  return useQuery({
    queryKey: ["cortex-memory"],
    queryFn: fetchCortexMemory,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

export function useCortexHealth() {
  return useQuery({
    queryKey: ["cortex-health"],
    queryFn: fetchCortexHealth,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

export function useCortexSemantic() {
  return useQuery({
    queryKey: ["cortex-semantic"],
    queryFn: fetchCortexSemantic,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

export function useExpansionSymbol(symbol: string) {
  const normalized = symbol.toUpperCase();
  return useQuery({
    queryKey: ["expansion-symbol", normalized],
    queryFn: () => fetchExpansionSymbol(normalized),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
    enabled: Boolean(normalized),
  });
}
