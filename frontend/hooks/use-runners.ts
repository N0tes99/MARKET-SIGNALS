"use client";

import { useQuery } from "@tanstack/react-query";

import {
  fetchCryptoRadar,
  fetchRunnerBacktest,
  fetchRunnerDetail,
  fetchRunnerLists,
  fetchRunnersFeed,
} from "@/services/api";

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

export function useCryptoRadar() {
  return useQuery({
    queryKey: ["crypto-radar"],
    queryFn: fetchCryptoRadar,
    staleTime: 90_000,
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

export function useRunnerBacktest(enabled: boolean) {
  return useQuery({
    queryKey: ["runners-backtest"],
    queryFn: fetchRunnerBacktest,
    staleTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    enabled,
  });
}
