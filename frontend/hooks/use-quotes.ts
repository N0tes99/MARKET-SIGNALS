"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchQuotes } from "@/services/api";

function isTabVisible(): boolean {
  if (typeof document === "undefined") return true;
  return document.visibilityState === "visible";
}

export function useQuotes() {
  return useQuery({
    queryKey: ["quotes"],
    queryFn: fetchQuotes,
    staleTime: 60_000,
    gcTime: 15 * 60_000,
    refetchInterval: () => (isTabVisible() ? 60_000 : false),
    refetchOnWindowFocus: true,
    placeholderData: (previous) => previous,
  });
}
