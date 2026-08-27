"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchRailDesk, simulateRailEnvelope } from "@/services/api";

export function useRailDesk() {
  return useQuery({
    queryKey: ["rail-desk"],
    queryFn: fetchRailDesk,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

export function useSimulateRailEnvelope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: simulateRailEnvelope,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["rail-desk"] });
    },
  });
}
