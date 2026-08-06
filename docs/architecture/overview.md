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

Analysis engines, decision pipeline (Opportunity / Execution / Risk), Learning Engine, AI Analyst, and backtesting are **implemented**. Dashboard rankings come from `GET /api/v1/assets` (TanStack Query poll); responses include `data_degraded` when market data is stale or providers fail repeatedly. Backend `WS /api/v1/ws/dashboard` exists; a frontend live client is deferred (Next.js API proxy does not upgrade WebSockets). Compose runs `celery-beat` for the warm-cache schedule. See `ARCHITECTURE.md` §3–§9 and `docs/roadmap/milestones.md`.

## Scoring Weights (Default)

| Category | Weight |
|----------|--------|
| Trend | 20 |
| Momentum | 15 |
| Volume | 10 |
| Structure | 20 |
| Risk | 15 |
| Macro | 10 |
| Derivatives | 10 |
| **Total** | **100** |

## Trade State Machine

```
IGNORE → WATCH → EXECUTE → MANAGE → EXIT
```

Pipeline resolver rules (see `DecisionPipelineService._resolve_trade_state`): Risk veto can hold EXECUTE back to WATCH; MANAGE/EXIT use learning open-signal context when available.
