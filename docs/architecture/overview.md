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

All engines are currently **placeholder stubs**. See `ARCHITECTURE.md` §3–§7 for planned interfaces and design rules.

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
