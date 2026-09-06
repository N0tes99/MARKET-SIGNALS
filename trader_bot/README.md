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
| Mode v0 | Paper sim + WS books + HTTP fallback |
| Live orders | Dual-control gated; `/exchange` signer not wired yet |

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

## Quick start (paper)

```bash
cd trader_bot
python3 -m pip install -e ".[dev]"
pytest
python3 -m hl_scalper.loop --mode paper --once --coins BTC
python3 -m hl_scalper.loop --mode paper --data-dir data          # WS on by default
python3 -m hl_scalper.loop --mode paper --data-dir data --no-ws  # HTTP only
python3 -m hl_scalper.report --journal data/journal.jsonl
```

Live mode stays gated (`LIVE_ENABLED`, `ALLOW_LIVE_ORDERS`, `data/ARMED`, agent key,
master **address** only). `/exchange` signer is not wired yet.

See [`docs/runbook.md`](docs/runbook.md) for systemd and journal layout.

## Safety

- No private keys in this repo.
- `LIVE_ENABLED` defaults false; live adapter raises.
- Kill switch trips on drawdown, error rate, or stale book.
- Live uses HL **agent wallet** (signs) vs **master wallet** (holds / withdraws) —
  see [`docs/automation-rails.md`](docs/automation-rails.md).
- Capital rules: [`docs/risk-policy.md`](docs/risk-policy.md)  
  Wallet research: [`docs/research/profitable-wallets.md`](docs/research/profitable-wallets.md)
