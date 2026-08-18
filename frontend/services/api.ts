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
  data_degraded?: boolean;
  data_age_seconds?: number | null;
  data_stale_reason?: string | null;
}

export type RankingStatus = "fresh" | "stale" | "warming";

export interface AssetsDashboard {
  assets: AssetSummary[];
  ranking_status: RankingStatus;
  cache_age_seconds?: number | null;
  as_of?: string | null;
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
  confidence?: number;
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
  data_degraded?: boolean;
  data_age_seconds?: number | null;
  data_stale_reason?: string | null;
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
  regime?: string | null;
  regime_confidence?: number | null;
}

const DEFAULT_FETCH_TIMEOUT_MS = 55_000;

/** Cookie auth through same-origin proxy or CORS-enabled local API. */
const FETCH_CREDENTIALS: RequestCredentials = "include";

async function readErrorJson(
  response: Response,
): Promise<{ detail?: unknown; code?: string } | null> {
  try {
    return (await response.json()) as { detail?: unknown; code?: string };
  } catch {
    return null;
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  const data = await readErrorJson(response);
  if (typeof data?.detail === "string") return data.detail;
  return `${response.status} ${response.statusText}`;
}

const GATE_SKIP_PATHS = [
  "/login",
  "/register",
  "/unlock",
  "/pending",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

function maybeRedirectGate(code: string | undefined): void {
  if (typeof window === "undefined" || !code) return;
  const path = window.location.pathname;
  if (GATE_SKIP_PATHS.some((p) => path === p || path.startsWith(`${p}/`))) return;
  const next = encodeURIComponent(`${path}${window.location.search}`);
  if (code === "MFA_REQUIRED") {
    window.location.replace(`/unlock?next=${next}`);
    return;
  }
  if (code === "LOGIN_REQUIRED") {
    window.location.replace(`/login?next=${next}`);
  }
}

async function apiFetch<T>(path: string, timeoutMs = DEFAULT_FETCH_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(apiUrl(path), {
      signal: controller.signal,
      credentials: FETCH_CREDENTIALS,
    });

    if (!response.ok) {
      const payload = await readErrorJson(response);
      maybeRedirectGate(payload?.code);
      if (response.status === 502 || response.status === 504) {
        throw new Error(
          `API timed out (${response.status}). The backend may still be warming up — retry in a minute.`,
        );
      }
      const detail = typeof payload?.detail === "string" ? payload.detail : null;
      throw new Error(detail ?? `API error: ${response.status} ${response.statusText}`);
    }

    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        `Request timed out after ${Math.round(timeoutMs / 1000)}s. Cold starts can take ~1 min — please retry.`,
      );
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/v1/health");
}

export async function fetchAssets(): Promise<AssetsDashboard> {
  // Default path is progressive (snapshot + background warm) — short budget.
  return apiFetch<AssetsDashboard>("/api/v1/assets", 20_000);
}

export async function fetchAsset(symbol: string): Promise<AssetSummary> {
  return apiFetch<AssetSummary>(`/api/v1/assets/${symbol}`);
}

export async function fetchEvidence(symbol: string): Promise<EvidenceBundle> {
  return apiFetch<EvidenceBundle>(`/api/v1/assets/${symbol}/evidence`);
}

export type SetupType = "funding_extreme" | "liq_flush" | "basis_rich";
export type SetupDirection = "long" | "short" | "neutral" | "relative";
export type SetupTradeStateHint = "IGNORE" | "WATCH";
export type SetupDataQuality = "good" | "degraded" | "missing";

export interface OpportunityIdea {
  id: string;
  symbol: string;
  instrument_type: "perp";
  setup_type: SetupType;
  direction_bias: SetupDirection;
  confidence: number;
  factors: string[];
  conflicts: string[];
  trade_state_hint: SetupTradeStateHint;
  as_of: string;
  data_quality: SetupDataQuality;
}

export interface AssetSetupsResponse {
  symbol: string;
  setups: OpportunityIdea[];
  scanned_at: string;
}

export async function fetchAssetSetups(symbol: string): Promise<AssetSetupsResponse> {
  return apiFetch<AssetSetupsResponse>(`/api/v1/assets/${symbol}/setups`);
}

export interface GlobalSetupsResponse {
  setups: OpportunityIdea[];
  scanned_at: string;
  symbols_scanned: number;
  watch_only: boolean;
  min_confidence: number;
}

export async function fetchSetupsFeed(opts?: {
  watchOnly?: boolean;
  minConfidence?: number;
}): Promise<GlobalSetupsResponse> {
  const watchOnly = opts?.watchOnly ?? true;
  const minConfidence = opts?.minConfidence ?? 55;
  const qs = new URLSearchParams({
    watch_only: String(watchOnly),
    min_confidence: String(minConfidence),
  });
  // Cold parallel crypto scan can be slow — align with assets budget.
  return apiFetch<GlobalSetupsResponse>(`/api/v1/setups?${qs}`, 110_000);
}

export interface PaperLedger {
  label: string;
  starting_cash: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  return_pct: number;
  open_positions: number;
  closed_trades: number;
  wins: number;
  losses: number;
  deployed_usd?: number;
  size_usd?: number;
}

export interface PaperTrade {
  id: string;
  symbol: string;
  source: string;
  setup_type: string;
  direction: string;
  fingerprint: string;
  signal_at: string;
  confidence: number;
  opportunity_score: number;
  size_usd: number;
  status: string;
  optimistic_entry: number;
  optimistic_entry_at: string;
  optimistic_exit: number | null;
  optimistic_pnl_usd: number | null;
  optimistic_return_pct: number | null;
  honest_entry: number | null;
  honest_entry_at: string | null;
  honest_bar_ts: string | null;
  honest_exit: number | null;
  honest_pnl_usd: number | null;
  honest_return_pct: number | null;
  mark_price: number | null;
  closed_at: string | null;
  close_reason: string | null;
  factors: string[];
  notes: string;
  signal_record_id?: string | null;
  take_profit_pct?: number;
  stop_loss_pct?: number;
  stamp?: string;
  policy?: {
    schema?: string;
    policy_id?: string;
    knobs?: Record<string, unknown>;
    features?: Record<string, unknown>;
    close?: Record<string, unknown>;
  };
}

export interface PaperMaturity {
  honest_closed: number;
  memory_outcomes: number;
  win_rate: number;
  avg_return_pct: number;
  expectancy_ok: boolean;
  max_drawdown_pct: number;
  drawdown_ok: boolean;
  target_honest_closed: number;
  target_memory_outcomes: number;
  score_pct: number;
  ready_for_private_live: boolean;
  blockers: string[];
}

export interface PaperSummary {
  agent_name: string;
  starting_cash: number;
  as_of: string;
  last_tick_at: string | null;
  optimistic: PaperLedger;
  honest: PaperLedger;
  open_trades: PaperTrade[];
  recent_closed: PaperTrade[];
  tick_notes: string[];
  maturity?: PaperMaturity | null;
  opens_today?: number;
  daily_open_cap?: number;
}

export async function fetchPaperSummary(tick = true): Promise<PaperSummary> {
  const qs = new URLSearchParams({ tick: String(tick) });
  return apiFetch<PaperSummary>(`/api/v1/paper/summary?${qs}`, 120_000);
}

export interface PerpsFundingRow {
  symbol: string;
  funding_rate: number | null;
  funding_bps: number | null;
  funding_trend_bps: number | null;
  open_interest: number | null;
  oi_change_pct: number | null;
  mark_price: number | null;
  source: string;
  available: boolean;
  note: string;
}

export interface PerpsLiquidationRow {
  symbol: string;
  long_usd: number | null;
  short_usd: number | null;
  total_usd: number | null;
  long_share: number | null;
  interval: string;
  score: number | null;
  description: string;
  available: boolean;
  coinglass_url: string | null;
}

export interface PerpsIdeaRow {
  id: string;
  symbol: string;
  setup_type: string;
  direction_bias: string;
  confidence: number;
  factors: string[];
  trade_state_hint: string;
}

export interface PerpsBoard {
  as_of: string;
  universe: string[];
  funding: PerpsFundingRow[];
  liquidations: PerpsLiquidationRow[];
  ideas: PerpsIdeaRow[];
  liquidations_configured: boolean;
  liquidations_note: string;
  funding_source: string;
  symbols_scanned: number;
  funding_filled: number;
  liquidations_filled: number;
}

export async function fetchPerpsBoard(): Promise<PerpsBoard> {
  return apiFetch<PerpsBoard>("/api/v1/perps/board", 100_000);
}

export type CmeFuturesBucket = "trending" | "extended" | "quiet";
export type CmeFuturesGroup =
  | "index"
  | "energy"
  | "metals"
  | "rates"
  | "fx"
  | "grains"
  | "crypto";

export interface CmeFuturesUniverseItem {
  symbol: string;
  name: string;
  group: CmeFuturesGroup;
}

export interface CmeFuturesRow {
  id: string;
  symbol: string;
  name: string;
  group: CmeFuturesGroup;
  bucket: CmeFuturesBucket;
  score: number;
  last: number | null;
  change_pct: number | null;
  volume: number | null;
  open_interest: number | null;
  expiry: string | null;
  mom_12h_pct: number | null;
  mom_20d_pct: number | null;
  relative_volume: number | null;
  factors: string[];
  conflicts: string[];
  as_of: string;
}

export interface CmeFuturesBoard {
  rows: CmeFuturesRow[];
  scanned_at: string;
  symbols_scanned: number;
  universe: CmeFuturesUniverseItem[];
  source: string;
}

export async function fetchCmeFuturesBoard(): Promise<CmeFuturesBoard> {
  return apiFetch<CmeFuturesBoard>("/api/v1/futures/board", 100_000);
}

export interface AlpacaAccount {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  status: string;
  currency: string;
}

export interface AlpacaPosition {
  symbol: string;
  qty: number;
  side: string;
  market_value: number;
  cost_basis: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  current_price: number;
  avg_entry_price: number;
  change_today: number;
}

export interface AlpacaFill {
  id: string;
  symbol: string;
  side: string;
  qty: number;
  filled_avg_price: number | null;
  filled_at: string | null;
  status: string;
  order_type: string;
  notional: number | null;
}

export interface AlpacaMirror {
  configured: boolean;
  mode: string;
  base_url: string;
  as_of: string;
  cached: boolean;
  error: string | null;
  account: AlpacaAccount | null;
  positions: AlpacaPosition[];
  recent_fills: AlpacaFill[];
}

export async function fetchAlpacaMirror(): Promise<AlpacaMirror> {
  return apiFetch<AlpacaMirror>("/api/v1/brokers/alpaca/mirror", 30_000);
}

export interface AlpacaActivityRow {
  symbol: string;
  last_price: number | null;
  daily_volume: number | null;
  change_pct: number | null;
  daily_bar_close: number | null;
  prev_close: number | null;
  trade_time: string | null;
}

export interface AlpacaActivity {
  configured: boolean;
  feed: string;
  data_base_url: string;
  as_of: string;
  cached: boolean;
  error: string | null;
  symbols_requested: string[];
  rows: AlpacaActivityRow[];
}

/** Free-tier IEX snapshots. Omit symbols to scan tracked stocks+ETFs. */
export async function fetchAlpacaActivity(symbols?: string[]): Promise<AlpacaActivity> {
  const qs =
    symbols && symbols.length > 0
      ? `?symbols=${encodeURIComponent(symbols.join(","))}`
      : "";
  return apiFetch<AlpacaActivity>(`/api/v1/brokers/alpaca/activity${qs}`, 30_000);
}

export interface PublicPreview {
  as_of: string;
  hot_picks: AssetSummary[];
  optimistic: PaperLedger;
  honest: PaperLedger;
  paper_as_of: string | null;
  last_tick_at: string | null;
}

export async function fetchPublicPreview(): Promise<PublicPreview> {
  return apiFetch<PublicPreview>("/api/v1/public/preview", 30_000);
}

export async function resetPaperAgent(): Promise<PaperSummary> {
  const response = await fetch(apiUrl("/api/v1/paper/reset"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<PaperSummary>;
}

export type EquitySetupType = "momentum_continuation" | "breakout_convexity";

export interface StagedEntry {
  step: number;
  label: string;
  size_pct: number;
  condition: string;
  price_trigger: number | null;
}

export interface ProfitZone {
  option_gain_pct: number;
  take_pct: number;
  label: string;
}

export interface ExecutionPlan {
  setup_name: string;
  direction: SetupDirection;
  max_risk_usd: number | null;
  entries: StagedEntry[];
  invalidation: string[];
  profit_zones: ProfitZone[];
  runner_pct: number;
  runner_rule?: string;
  notes: string;
}

export interface OptionCandidate {
  underlying: string;
  expiry: string;
  strike: number;
  right: "call" | "put";
  bid: number | null;
  ask: number | null;
  mid: number | null;
  volume: number | null;
  open_interest: number | null;
  iv: number | null;
  otm_pct: number;
  dte: number;
  convexity_score: number;
  liquidity_score: number;
  theta_score: number;
  iv_value_score: number;
  overall_score: number;
  rationale: string;
}

export interface EquityOptionsIdea {
  id: string;
  symbol: string;
  instrument_type: "equity_option";
  setup_type: EquitySetupType;
  direction_bias: SetupDirection;
  confidence: number;
  opportunity_score: number;
  factors: string[];
  conflicts: string[];
  trade_state_hint: SetupTradeStateHint;
  momentum_score: number;
  catalyst_score: number;
  liquidity_score: number;
  option_candidates: OptionCandidate[];
  selected_option: OptionCandidate | null;
  execution_plan: ExecutionPlan | null;
  as_of: string;
  data_quality: SetupDataQuality;
}

export interface AssetEquitySetupsResponse {
  symbol: string;
  setups: EquityOptionsIdea[];
  scanned_at: string;
}

export interface GlobalEquitySetupsResponse {
  setups: EquityOptionsIdea[];
  scanned_at: string;
  symbols_scanned: number;
  watch_only: boolean;
  min_confidence: number;
}

export async function fetchEquitySetupsFeed(opts?: {
  watchOnly?: boolean;
  minConfidence?: number;
}): Promise<GlobalEquitySetupsResponse> {
  const watchOnly = opts?.watchOnly ?? true;
  const minConfidence = opts?.minConfidence ?? 55;
  const qs = new URLSearchParams({
    watch_only: String(watchOnly),
    min_confidence: String(minConfidence),
  });
  return apiFetch<GlobalEquitySetupsResponse>(`/api/v1/equity-setups?${qs}`, 120_000);
}

export async function fetchAssetEquitySetups(
  symbol: string,
): Promise<AssetEquitySetupsResponse> {
  return apiFetch<AssetEquitySetupsResponse>(
    `/api/v1/assets/${symbol}/equity-setups`,
    90_000,
  );
}

export type TapeHeat = "hot" | "warm";

export interface TapeHunt {
  id: string;
  symbol: string;
  direction: "long" | "short";
  heat: TapeHeat;
  hunt_score: number;
  relative_volume: number;
  range_expansion: number;
  ret_5d_pct: number;
  ret_20d_pct: number;
  put_call_vol: number;
  option_volume: number;
  unusual_vol_oi: number;
  factors: string[];
  conflicts: string[];
  selected_option: OptionCandidate | null;
  option_candidates: OptionCandidate[];
  execution_plan: ExecutionPlan | null;
  as_of: string;
}

export interface TapeBoardResponse {
  longs: TapeHunt[];
  shorts: TapeHunt[];
  symbols_scanned: number;
  symbols_optioned: number;
  per_side: number;
  scanned_at: string;
  note: string;
}

export async function fetchOptionsTape(opts?: {
  perSide?: number;
  add?: string;
}): Promise<TapeBoardResponse> {
  const qs = new URLSearchParams({
    per_side: String(opts?.perSide ?? 5),
  });
  if (opts?.add) qs.set("add", opts.add);
  return apiFetch<TapeBoardResponse>(`/api/v1/options-tape?${qs}`, 120_000);
}

export type RunnerStage =
  | "dormant"
  | "fundamental_inflection"
  | "early_accumulation"
  | "catalyst"
  | "ignition"
  | "discovery"
  | "momentum"
  | "extended";

export type RunnerWatchlist = "early" | "ignition" | "running" | "none";
export type RunnerDataQuality = "good" | "degraded" | "missing";

export interface RunnerScores {
  fundamental: number;
  catalyst: number;
  structure: number;
  asymmetry: number;
  discovery_gap: number;
  theme_bottleneck: number;
  institutional_accum: number;
  short_squeeze_potential: number;
  runner_score: number;
  risk_score: number;
  penalties: number;
}

export interface RunnerCandidate {
  id: string;
  symbol: string;
  instrument_type: "runner";
  stage: RunnerStage;
  signal_type: string;
  watchlist: RunnerWatchlist;
  scores: RunnerScores;
  factors: string[];
  conflicts: string[];
  risk_flags: string[];
  confidence: number;
  data_quality: RunnerDataQuality;
  as_of: string;
  phase: string;
  qualities: Record<string, RunnerDataQuality>;
  ret_20d_pct: number | null;
  relative_volume: number | null;
  rs_benchmark: string | null;
  rs_pct: number | null;
}

export interface RunnerFeedResponse {
  candidates: RunnerCandidate[];
  scanned_at: string;
  symbols_scanned: number;
  fundamentals_filled?: number;
  fundamentals_missing?: number;
  watchlist: RunnerWatchlist | null;
  min_runner_score: number;
  stage: RunnerStage | null;
}

export interface RunnerListsResponse {
  early: RunnerCandidate[];
  ignition: RunnerCandidate[];
  running: RunnerCandidate[];
  scanned_at: string;
  symbols_scanned: number;
  fundamentals_filled?: number;
  fundamentals_missing?: number;
}

export interface RunnerDetailResponse {
  candidate: RunnerCandidate;
  scanned_at: string;
}

export async function fetchRunnersFeed(): Promise<RunnerFeedResponse> {
  return apiFetch<RunnerFeedResponse>("/api/v1/runners", 120_000);
}

export async function fetchRunnerLists(): Promise<RunnerListsResponse> {
  return apiFetch<RunnerListsResponse>("/api/v1/runners/lists", 120_000);
}

export async function fetchRunnerDetail(symbol: string): Promise<RunnerDetailResponse> {
  return apiFetch<RunnerDetailResponse>(`/api/v1/runners/${symbol}`, 90_000);
}

export type CryptoRadarBucket = "watch" | "crowded" | "running" | "none";

export interface CryptoRadarCandidate {
  id: string;
  symbol: string;
  bucket: CryptoRadarBucket;
  score: number;
  factors: string[];
  conflicts: string[];
  mom_12h_pct: number | null;
  mom_20d_pct: number | null;
  funding_bps: number | null;
  oi_change_pct: number | null;
  funding_source: string;
  mark_price: number | null;
  basis_pct: number | null;
  as_of: string;
}

export interface CryptoRadarFeedResponse {
  candidates: CryptoRadarCandidate[];
  watch: CryptoRadarCandidate[];
  crowded: CryptoRadarCandidate[];
  running: CryptoRadarCandidate[];
  scanned_at: string;
  symbols_scanned: number;
  funding_filled: number;
  universe: string[];
  coefficients_preset: string;
  perp_momentum_n: number;
  perp_momentum_win_rate: number | null;
}

export async function fetchCryptoRadar(): Promise<CryptoRadarFeedResponse> {
  return apiFetch<CryptoRadarFeedResponse>("/api/v1/runners/crypto", 120_000);
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
    credentials: FETCH_CREDENTIALS,
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
      credentials: FETCH_CREDENTIALS,
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
  regime_auto?: boolean;
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

export interface AssetQuote {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  as_of: string | null;
  available: boolean;
}

export interface CandlePoint {
  t: string;
  o: number;
  h: number;
  low: number;
  c: number;
  v: number;
}

export interface CandleSeries {
  symbol: string;
  timeframe: string;
  candles: CandlePoint[];
}

export async function fetchQuotes(): Promise<AssetQuote[]> {
  return apiFetch<AssetQuote[]>("/api/v1/quotes");
}

export async function fetchQuote(symbol: string): Promise<AssetQuote> {
  return apiFetch<AssetQuote>(`/api/v1/quotes/${symbol}`);
}

export async function fetchCandles(
  symbol: string,
  timeframe: string = "15m",
  limit: number = 96,
): Promise<CandleSeries> {
  const params = new URLSearchParams({
    timeframe,
    limit: String(limit),
  });
  return apiFetch<CandleSeries>(`/api/v1/quotes/${symbol}/candles?${params}`);
}

export async function applyWeightPreset(preset: string): Promise<ActiveWeights> {
  const response = await fetch(apiUrl("/api/v1/tuning/weights/apply"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset }),
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json() as Promise<ActiveWeights>;
}

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  email_verified: boolean;
  created_at: string;
  is_admin?: boolean;
}

export interface DiscussionComment {
  id: string;
  post_id: string;
  user_id: string;
  username: string;
  body: string;
  created_at: string;
}

export interface DiscussionPost {
  id: string;
  user_id: string;
  username: string;
  symbol: string;
  body: string;
  created_at: string;
  comments: DiscussionComment[];
  comment_count: number;
  like_count: number;
  liked_by_me: boolean;
  is_shredded?: boolean;
  shredded_at?: string | null;
}

export interface PublicProfile {
  id: string;
  username: string;
  created_at: string;
  follower_count: number;
  following_count: number;
  post_count: number;
  followed_by_me: boolean;
}

export interface FavoriteSymbol {
  symbol: string;
  created_at: string;
}

export interface GateStatus {
  enabled: boolean;
  expire_hours: number;
  authenticated: boolean;
  is_admin: boolean;
  granted: boolean;
  grant_expires_at: string | null;
  mfa_ok: boolean;
  next_step: "open" | "login" | "pending" | "enroll" | "mfa" | "dashboard";
  totp_enrolled?: boolean;
}

export interface AccessGrant {
  id: string;
  user_id: string;
  username: string;
  email: string;
  expires_at: string;
  notes: string;
  revoked_at: string | null;
  created_at: string;
  active: boolean;
}

export interface WaitlistUser {
  id: string;
  username: string;
  email: string;
  created_at: string;
  email_verified: boolean;
}

export interface WalletAccessUser {
  user_id: string;
  username: string;
  chain: string;
  address: string;
  created_at: string;
  granted: boolean;
  grant_id: string | null;
  grant_expires_at: string | null;
}

export async function fetchGateStatus(): Promise<GateStatus> {
  const response = await fetch(apiUrl("/api/v1/auth/gate/status"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<GateStatus>;
}

export async function verifySiteGate(code: string): Promise<{
  ok: boolean;
  next_step: string;
  grant_expires_at: string | null;
}> {
  const response = await fetch(apiUrl("/api/v1/auth/gate/verify"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json();
}

export interface GateEnroll {
  enrolled: boolean;
  secret: string | null;
  otpauth_uri: string | null;
  issuer: string;
  account: string;
}

export async function fetchGateEnroll(): Promise<GateEnroll> {
  const response = await fetch(apiUrl("/api/v1/auth/gate/enroll"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<GateEnroll>;
}

export interface AccessHealth {
  reddit: boolean;
  fred: boolean;
  gemini: boolean;
  discord: boolean;
  alert_enabled: boolean;
  cron_secret: boolean;
  strip: string;
}

export async function fetchAccessHealth(): Promise<AccessHealth> {
  const response = await fetch(apiUrl("/api/v1/auth/access/health"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AccessHealth>;
}

export async function sendAlertTest(
  channel: "discord" | "email" | "both" | "paper" = "discord",
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/api/v1/alerts/test"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<Record<string, unknown>>;
}

export async function fetchAccessGrants(): Promise<AccessGrant[]> {
  const response = await fetch(apiUrl("/api/v1/auth/access/grants"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AccessGrant[]>;
}

export async function fetchWaitlistUsers(): Promise<WaitlistUser[]> {
  const response = await fetch(apiUrl("/api/v1/auth/access/waitlist"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<WaitlistUser[]>;
}

export async function fetchAccessWallets(): Promise<WalletAccessUser[]> {
  const response = await fetch(apiUrl("/api/v1/auth/access/wallets"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<WalletAccessUser[]>;
}

export async function createAccessGrant(body: {
  username: string;
  expires_at: string;
  notes?: string;
}): Promise<AccessGrant> {
  const response = await fetch(apiUrl("/api/v1/auth/access/grants"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AccessGrant>;
}

export async function revokeAccessGrant(grantId: string): Promise<AccessGrant> {
  const response = await fetch(apiUrl(`/api/v1/auth/access/grants/${grantId}/revoke`), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AccessGrant>;
}

export async function fetchMe(): Promise<AuthUser | null> {
  const response = await fetch(apiUrl("/api/v1/auth/me"), {
    credentials: FETCH_CREDENTIALS,
  });
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AuthUser>;
}

export async function registerAccount(
  email: string,
  username: string,
  password: string,
): Promise<AuthUser> {
  const response = await fetch(apiUrl("/api/v1/auth/register"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username, password }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AuthUser>;
}

export async function loginAccount(email: string, password: string): Promise<AuthUser> {
  const response = await fetch(apiUrl("/api/v1/auth/login"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AuthUser>;
}

export async function walletChallenge(body: {
  chain?: string;
  address: string;
  chain_id?: number;
}): Promise<{
  chain: string;
  address: string;
  nonce: string;
  message: string;
  expires_at: string;
}> {
  const response = await fetch(apiUrl("/api/v1/auth/wallet/challenge"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chain: body.chain ?? "ethereum",
      address: body.address,
      chain_id: body.chain_id ?? 1,
    }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json();
}

export async function walletVerify(body: {
  chain?: string;
  address: string;
  signature: string;
  nonce: string;
}): Promise<AuthUser> {
  const response = await fetch(apiUrl("/api/v1/auth/wallet/verify"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chain: body.chain ?? "ethereum",
      address: body.address,
      signature: body.signature,
      nonce: body.nonce,
    }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AuthUser>;
}

export async function logoutAccount(): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/auth/logout"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function verifyEmailToken(token: string): Promise<AuthUser> {
  const response = await fetch(apiUrl("/api/v1/auth/verify-email"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AuthUser>;
}

export async function resendVerification(email?: string): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/auth/resend-verification"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(email ? { email } : {}),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function forgotPassword(email: string): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/auth/forgot-password"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function resetPassword(token: string, password: string): Promise<AuthUser> {
  const response = await fetch(apiUrl("/api/v1/auth/reset-password"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<AuthUser>;
}

export async function fetchAssetPosts(symbol: string): Promise<DiscussionPost[]> {
  return apiFetch<DiscussionPost[]>(`/api/v1/assets/${symbol}/posts`);
}

export async function fetchSocialFeed(): Promise<DiscussionPost[]> {
  return apiFetch<DiscussionPost[]>("/api/v1/social/feed");
}

export async function createAssetPost(symbol: string, body: string): Promise<DiscussionPost> {
  const response = await fetch(apiUrl(`/api/v1/assets/${symbol}/posts`), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<DiscussionPost>;
}

export async function createFeedPost(symbol: string, body: string): Promise<DiscussionPost> {
  const response = await fetch(apiUrl("/api/v1/social/posts"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, body }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<DiscussionPost>;
}

export async function createPostComment(
  postId: string,
  body: string,
): Promise<DiscussionComment> {
  const response = await fetch(apiUrl(`/api/v1/posts/${postId}/comments`), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<DiscussionComment>;
}

export async function likePost(postId: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/posts/${postId}/like`), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function unlikePost(postId: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/posts/${postId}/like`), {
    method: "DELETE",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function shredPost(
  postId: string,
  reason?: string,
): Promise<DiscussionPost> {
  const response = await fetch(apiUrl(`/api/v1/posts/${postId}/shred`), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason ?? null }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<DiscussionPost>;
}

export async function fetchPublicProfile(username: string): Promise<PublicProfile> {
  return apiFetch<PublicProfile>(`/api/v1/users/${encodeURIComponent(username)}`);
}

export async function followUser(userId: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/users/${userId}/follow`), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function unfollowUser(userId: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/users/${userId}/follow`), {
    method: "DELETE",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(await readErrorDetail(response));
  }
}

export async function fetchFavorites(): Promise<FavoriteSymbol[]> {
  const response = await fetch(apiUrl("/api/v1/me/favorites"), {
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<FavoriteSymbol[]>;
}

export async function addFavorite(symbol: string): Promise<FavoriteSymbol> {
  const response = await fetch(apiUrl("/api/v1/me/favorites"), {
    method: "PUT",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<FavoriteSymbol>;
}

export async function removeFavorite(symbol: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/me/favorites/${encodeURIComponent(symbol)}`), {
    method: "DELETE",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(await readErrorDetail(response));
  }
}

export interface TickerRequest {
  id: string;
  user_id: string;
  username: string;
  symbol: string;
  message: string;
  status: string;
  admin_note: string;
  created_at: string;
  resolved_at: string | null;
}

export async function createTickerRequest(body: {
  symbol: string;
  message?: string;
}): Promise<TickerRequest> {
  const response = await fetch(apiUrl("/api/v1/ticker-requests"), {
    method: "POST",
    credentials: FETCH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: body.symbol,
      message: body.message ?? "",
    }),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<TickerRequest>;
}

export async function fetchMyTickerRequests(): Promise<TickerRequest[]> {
  const response = await fetch(apiUrl("/api/v1/ticker-requests/mine"), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<TickerRequest[]>;
}

export async function fetchAdminTickerRequests(
  status?: string,
): Promise<TickerRequest[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await fetch(apiUrl(`/api/v1/ticker-requests/admin${qs}`), {
    credentials: FETCH_CREDENTIALS,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<TickerRequest[]>;
}

export async function resolveTickerRequest(
  requestId: string,
  body: { status: "done" | "dismissed" | "open"; admin_note?: string },
): Promise<TickerRequest> {
  const response = await fetch(
    apiUrl(`/api/v1/ticker-requests/admin/${requestId}/resolve`),
    {
      method: "POST",
      credentials: FETCH_CREDENTIALS,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: body.status,
        admin_note: body.admin_note ?? "",
      }),
    },
  );
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json() as Promise<TickerRequest>;
}
