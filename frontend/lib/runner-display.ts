import type { RunnerCandidate, RunnerDataQuality } from "@/services/api";

export function dimDisplay(candidate: RunnerCandidate, key: keyof RunnerCandidate["scores"]): string {
  const quality: RunnerDataQuality | undefined = candidate.qualities[key];
  if (quality === "missing") return "—";
  const value = candidate.scores[key];
  if (typeof value !== "number") return "—";
  return value.toFixed(0);
}

export function formatTapePct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

export function formatRelVol(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}×`;
}
