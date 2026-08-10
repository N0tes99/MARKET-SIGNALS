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

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
  } catch {
    /* ignore */
  }
  return `${response.status} ${response.statusText}`;
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
      if (response.status === 502 || response.status === 504) {
        throw new Error(
          `API timed out (${response.status}). The backend may still be warming up — retry in a minute.`,
        );
      }
      throw new Error(`API error: ${response.status} ${response.statusText}`);
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

export async function fetchAssets(): Promise<AssetSummary[]> {
  // Match Netlify proxy budget for cold rank_all (see backend/[...path]/route.ts).
  return apiFetch<AssetSummary[]>("/api/v1/assets", 110_000);
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
}

export async function fetchPaperSummary(tick = true): Promise<PaperSummary> {
  const qs = new URLSearchParams({ tick: String(tick) });
  return apiFetch<PaperSummary>(`/api/v1/paper/summary?${qs}`, 120_000);
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
  limit: number = 48,
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
