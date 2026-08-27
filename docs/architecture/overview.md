# Architecture Summary

> **Full documentation:** See [`ARCHITECTURE.md`](../../ARCHITECTURE.md) at the project root.

This file is a quick-reference summary. The root `ARCHITECTURE.md` is the authoritative source of truth for all system design decisions, interfaces, and implementation status.

## Data Flow

```
Market Data → [Specialized Engines] → Evidence Engine → Opportunity Engine
                                                    ↓
                                              Execution Engine
                                                    ↓
                                               Risk Engine
                                                    ↓
                                               AI Analyst → Dashboard
```

## Engine Status

Analysis engines, decision pipeline (Opportunity / Execution / Risk), Learning Engine, AI Analyst, chart screenshot analyzer, and backtesting are **implemented**. Dashboard rankings come from `GET /api/v1/assets` (TanStack Query poll); responses include `data_degraded` when market data is stale or providers fail repeatedly. Backend `WS /api/v1/ws/dashboard` exists; a frontend live client is deferred (Next.js API proxy does not upgrade WebSockets). Compose runs `celery-beat` for the warm-cache schedule. See `ARCHITECTURE.md` §3–§9 and `docs/roadmap/milestones.md`.

**Surfaces:** (1) asset ranking, (2) crypto setups, (3) equity options (MVP), (4) Runner Detection / 10X Radar — **Phase 2 preview**. (5) Expansion radar + cortex. (6) **Rail Engine** — Hyperliquid-native discovery + blind clerk (`/rail`); Phase B scanners, paper dry-run. Plan: `docs/research/rail-execution-surface.md`. Surfaces 1–5 stay intelligence-only.

## Scoring Weights (Default)

13 categories normalized to 100. Core seven (Structure / Momentum / Trend / Risk / Volume / Macro / Derivatives) are relative shares of ~80–85; residual ~15–20 across Correlation, Volatility, Events, Sector RS, On-Chain, Sentiment. See `DEFAULT_WEIGHTS` and `REGIME_WEIGHT_PROFILES` in `backend/app/scoring/weights.py`. Regime swaps full profiles (Trending / Choppy / High-vol); item `confidence` defaults to 1.0.

## Trade State Machine

```
IGNORE → WATCH → EXECUTE → MANAGE → EXIT
```

Pipeline resolver rules (see `DecisionPipelineService._resolve_trade_state`): Risk veto can hold EXECUTE back to WATCH; MANAGE/EXIT use learning open-signal context when available.
