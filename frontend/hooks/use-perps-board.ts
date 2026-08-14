"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchPerpsBoard } from "@/services/api";

export function usePerpsBoard() {
  return useQuery({
    queryKey: ["perps-board"],
    queryFn: () => fetchPerpsBoard(),
    staleTime: 90_000,
    refetchOnWindowFocus: false,
  });
}
