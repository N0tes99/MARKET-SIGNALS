/**
 * API base URL.
 * - Local default: direct FastAPI at NEXT_PUBLIC_API_URL
 * - Deploy: set NEXT_PUBLIC_USE_API_PROXY=true so the browser hits
 *   same-origin /api/backend (server injects Basic Auth).
 */
const USE_API_PROXY = process.env.NEXT_PUBLIC_USE_API_PROXY === "true";
const API_BASE_URL = USE_API_PROXY
  ? "/api/backend"
  : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export interface AssetSummary {
  symbol: string;
  confidence: number;
  trend: string;
  trade_grade: string;
  buyer_strength: number;
  risk: number;
  expected_value: number;
  trade_state: string;
  execution_signal: string;
  asset_class: "crypto" | "stock" | "etf";
}

export interface OpportunitySummary {
  symbol: string;
  opportunity_score: number;
  trade_grade: string;
  expected_value: number;
  trade_state: string;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
}

export interface EvidenceItem {
  source: string;
  category: string;
  score: number;
  weight: number;
  description: string;
}

export interface AIExplanation {
  symbol: string;
  summary: string;
  confidence: number;
  factors: string[];
  conflicts: string[];
  source: string;
  generated_at: string;
}

export interface DecisionResult {
  symbol: string;
  opportunity_score: number;
  trade_grade: string;
  expected_value: number;
  trade_state: string;
  execution: {
    signal: string;
    confidence: number;
    description: string;
  };
  summary: string;
  risk?: {
    stop_loss: number;
    take_profit: number;
    risk_reward_ratio: number;
    score: number;
    description: string;
  };
}

export interface SimilarMatch {
  id: string;
  symbol: string;
  timestamp: string;
  confidence: number;
  trade_grade: string;
  trade_state: string;
  similarity: number;
  category_scores: Record<string, number>;
  outcome?: string | null;
  realized_return_pct?: number | null;
}

export interface SignalRecord {
  id: string;
  symbol: string;
  timestamp: string;
  confidence: number;
  trade_grade: string;
  trade_state: string;
  execution_signal: string;
  opportunity_score: number;
  category_scores: Record<string, number>;
  expected_value?: number | null;
  entry_price?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  outcome?: string | null;
  realized_return_pct?: number | null;
  notes?: string | null;
  resolved_at?: string | null;
}

export type SignalOutcome = "win" | "loss" | "breakeven" | "no_trade";

export interface OutcomeStats {
  symbol: string;
  total_logged: number;
  resolved: number;
  open: number;
  wins: number;
  losses: number;
  breakeven: number;
  no_trade: number;
  win_rate: number;
  avg_return_pct: number;
}

export interface SimilarityResponse {
  symbol: string;
  matches: SimilarMatch[];
  history_count: number;
}

export interface BacktestResult {
  symbol: string;
  timeframe: string;
  hold_bars: number;
  signal_threshold: number;
  total_signals: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_return_pct: number;
  best_return_pct: number;
  worst_return_pct: number;
  description: string;
}

export interface EvidenceBundle {
  id: string;
  symbol: string;
  timeframe: string;
  total_confidence: number;
  items: EvidenceItem[];
  timestamp: string;
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path));

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/v1/health");
}

export async function fetchAssets(): Promise<AssetSummary[]> {
  return apiFetch<AssetSummary[]>("/api/v1/assets");
}

export async function fetchAsset(symbol: string): Promise<AssetSummary> {
  return apiFetch<AssetSummary>(`/api/v1/assets/${symbol}`);
}

export async function fetchOpportunities(): Promise<OpportunitySummary[]> {
  return apiFetch<OpportunitySummary[]>("/api/v1/opportunities");
}

export async function fetchEvidence(symbol: string): Promise<EvidenceBundle> {
  return apiFetch<EvidenceBundle>(`/api/v1/assets/${symbol}/evidence`);
}

export async function fetchAnalysis(symbol: string): Promise<AIExplanation> {
  return apiFetch<AIExplanation>(`/api/v1/assets/${symbol}/analysis`);
}

export async function fetchDecision(symbol: string): Promise<DecisionResult> {
  return apiFetch<DecisionResult>(`/api/v1/assets/${symbol}/decision`);
}

export async function fetchSimilarity(symbol: string): Promise<SimilarityResponse> {
  return apiFetch<SimilarityResponse>(`/api/v1/assets/${symbol}/similarity`);
}

export async function fetchSignals(symbol: string, limit = 20): Promise<SignalRecord[]> {
  return apiFetch<SignalRecord[]>(`/api/v1/assets/${symbol}/signals?limit=${limit}`);
}

export async function logCurrentSignal(symbol: string): Promise<SignalRecord> {
  const response = await fetch(apiUrl(`/api/v1/assets/${symbol}/signals/log`), {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json() as Promise<SignalRecord>;
}

export async function recordSignalOutcome(
  symbol: string,
  recordId: string,
  outcome: SignalOutcome,
  realizedReturnPct?: number | null,
  notes?: string | null,
): Promise<SignalRecord> {
  const response = await fetch(
    apiUrl(`/api/v1/assets/${symbol}/signals/${recordId}/outcome`),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        outcome,
        realized_return_pct: realizedReturnPct ?? null,
        notes: notes ?? null,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json() as Promise<SignalRecord>;
}

export async function fetchOutcomeStats(symbol: string): Promise<OutcomeStats> {
  return apiFetch<OutcomeStats>(`/api/v1/assets/${symbol}/outcomes/stats`);
}

export async function fetchBacktest(symbol: string): Promise<BacktestResult> {
  return apiFetch<BacktestResult>(`/api/v1/backtests/${symbol}`);
}

export interface WeightTuningResult {
  symbol: string;
  timeframe: string;
  active_preset: string;
  active_weights: Record<string, number>;
  recommended_preset: string;
  recommended_weights: Record<string, number>;
  results: Array<{
    preset_name: string;
    weights: Record<string, number>;
    total_signals: number;
    win_rate: number;
    avg_return_pct: number;
    score: number;
  }>;
}

export interface ActiveWeights {
  preset: string;
  weights: Record<string, number>;
}

export async function fetchWeightTuning(symbol: string): Promise<WeightTuningResult> {
  return apiFetch<WeightTuningResult>(`/api/v1/tuning/optimize/${symbol}`);
}

export interface AlertStatus {
  enabled: boolean;
  min_confidence: number;
  min_grade: string;
  cooldown_minutes: number;
  discord_configured: boolean;
  discord_mode: "bot" | "webhook" | "both" | "none" | string;
  email_configured: boolean;
  channels: {
    discord: boolean;
    email: boolean;
  };
}

export async function fetchAlertStatus(): Promise<AlertStatus> {
  return apiFetch<AlertStatus>("/api/v1/alerts/status");
}

export async function applyWeightPreset(preset: string): Promise<ActiveWeights> {
  const response = await fetch(apiUrl("/api/v1/tuning/weights/apply"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset }),
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json() as Promise<ActiveWeights>;
}
