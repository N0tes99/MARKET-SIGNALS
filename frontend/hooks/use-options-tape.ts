"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchOptionsTape } from "@/services/api";

export function useOptionsTape(perSide = 5) {
  return useQuery({
    queryKey: ["options-tape", perSide],
    queryFn: () => fetchOptionsTape({ perSide }),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}
