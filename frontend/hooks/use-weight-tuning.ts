"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyWeightPreset, fetchWeightTuning } from "@/services/api";

export function useWeightTuning(symbol: string) {
  return useQuery({
    queryKey: ["weight-tuning", symbol],
    queryFn: () => fetchWeightTuning(symbol),
    staleTime: 10 * 60_000,
  });
}

export function useApplyWeights(symbol: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: applyWeightPreset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["evidence", symbol] });
      queryClient.invalidateQueries({ queryKey: ["decision", symbol] });
      queryClient.invalidateQueries({ queryKey: ["weight-tuning", symbol] });
    },
  });
}
