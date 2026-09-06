# HL Scalper (side project)

Isolated Hyperliquid **book-imbalance scalping** sandbox. Lives next to Signal Engine;
does **not** modify `backend/`, `frontend/`, or Rail production code.

## Why this exists

Signal Engine is a research desk. Rail Phase B already scans HL L2 imbalance and
paper-acks envelopes — but it is not a latency-aware scalp loop, and live
`/exchange` is hard-refused.

This folder is the place to prove (or kill) a **microstructure scalp** edge on
Hyperliquid before any signing wallet exists.

## Decisions (locked)

| Choice | Value |
|--------|--------|
| Venue | Hyperliquid perps only |
| Edge | L2 book imbalance / micro-scalp |
| Mode v0 | Paper sim + read-only `/info` (+ WS later) |
| Live orders | Disabled. Stub refuses always. |

## Layout

```
trader_bot/
  PLAN.md                 phased roadmap
  docs/architecture.md    loop, risk, data flow
  src/hl_scalper/         Python package (standalone)
  tests/                  unit tests (no live network required)
```

## Relationship to Signal Engine

| Reuse as reference | Do not import / couple yet |
|--------------------|----------------------------|
| `engines/rail/scanners/book.py` imbalance math | SE Celery, FastAPI, Postgres |
| `engines/rail/adapters/hyperliquid_info.py` | Rail clerk / blind envelopes |
| Rail kill-switch philosophy | Production deploy paths |

Copy ideas; keep this package importable on its own (`cd trader_bot && pip install -e .`).

## Quick start (when implemented)

```bash
cd trader_bot
python -m pip install -e ".[dev]"
pytest
python -m hl_scalper.loop --mode paper --coins BTC,ETH
```

## Safety

- No private keys in this repo.
- `LIVE_ENABLED` defaults false; live adapter raises.
- Kill switch trips on drawdown, error rate, or stale book.
