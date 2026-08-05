"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchQuotes } from "@/services/api";

export function useQuotes() {
  return useQuery({
    queryKey: ["quotes"],
    queryFn: fetchQuotes,
    staleTime: 45_000,
    gcTime: 10 * 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });
}
