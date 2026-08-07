"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAssetSetups } from "@/services/api";

export function useSetups(symbol: string) {
  return useQuery({
    queryKey: ["setups", symbol],
    queryFn: () => fetchAssetSetups(symbol),
    staleTime: 90_000,
    refetchOnWindowFocus: false,
  });
}
