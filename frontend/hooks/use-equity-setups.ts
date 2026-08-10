"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAssetEquitySetups } from "@/services/api";

export function useEquitySetups(symbol: string) {
  return useQuery({
    queryKey: ["equity-setups", symbol],
    queryFn: () => fetchAssetEquitySetups(symbol),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}
