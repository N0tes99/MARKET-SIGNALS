"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchBacktest } from "@/services/api";

export function useBacktest(symbol: string) {
  return useQuery({
    queryKey: ["backtest", symbol],
    queryFn: () => fetchBacktest(symbol),
    staleTime: 5 * 60_000,
  });
}
