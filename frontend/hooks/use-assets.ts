"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAssets } from "@/services/api";

export function useAssets() {
  return useQuery({
    queryKey: ["assets"],
    queryFn: fetchAssets,
    staleTime: 90_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}
