"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchOptionsTape } from "@/services/api";

export function useOptionsTape(perSide = 5, extras: string[] = []) {
  const add = extras.join(",");
  return useQuery({
    queryKey: ["options-tape", perSide, add],
    queryFn: () => fetchOptionsTape({ perSide, add: add || undefined }),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}
