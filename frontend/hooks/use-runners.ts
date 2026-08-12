"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchRunnerDetail, fetchRunnerLists, fetchRunnersFeed } from "@/services/api";

export function useRunnersFeed() {
  return useQuery({
    queryKey: ["runners-feed"],
    queryFn: fetchRunnersFeed,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}

export function useRunnerLists() {
  return useQuery({
    queryKey: ["runners-lists"],
    queryFn: fetchRunnerLists,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}

export function useRunnerDetail(symbol: string) {
  const normalized = symbol.toUpperCase();
  return useQuery({
    queryKey: ["runner-detail", normalized],
    queryFn: () => fetchRunnerDetail(normalized),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
    enabled: Boolean(normalized),
  });
}
