"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchQuotes } from "@/services/api";

export function useQuotes() {
  return useQuery({
    queryKey: ["quotes"],
    queryFn: fetchQuotes,
    staleTime: 90_000,
    gcTime: 15 * 60_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
    placeholderData: (previous) => previous,
  });
}
