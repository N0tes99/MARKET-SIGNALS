"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchCmeFuturesBoard } from "@/services/api";

export function useFuturesBoard() {
  return useQuery({
    queryKey: ["cme-futures-board"],
    queryFn: () => fetchCmeFuturesBoard(),
    staleTime: 90_000,
    refetchOnWindowFocus: false,
  });
}
