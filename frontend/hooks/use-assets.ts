"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchAssets } from "@/services/api";

export function useAssets() {
  return useQuery({
    queryKey: ["assets"],
    queryFn: fetchAssets,
    staleTime: 120_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: (previous) => previous,
  });
}
