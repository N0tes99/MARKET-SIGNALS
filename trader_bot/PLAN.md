# Plan — Hyperliquid book-imbalance scalper

Status: **scaffolding / Phase 0**  
Venue: Hyperliquid perps  
Edge: L2 book imbalance scalping  
Last updated: 2026-09-06

## Goal

Build a separate process that can **gradually compound** paper (then tiny live)
equity by harvesting short-lived L2 imbalances on Hyperliquid — with ruthless
risk gates so a bad day cannot erase the account.

Signal Engine stays the desk. This folder is the **execution lab**.

---

## Phase 0 — Scaffold (this PR)

- [x] Top-level `trader_bot/` only (no `backend/` / `frontend/` edits)
- [x] Architecture doc + module stubs
- [x] Paper sim types + imbalance signal (ported from Rail book scanner math)
- [x] Live venue stub that always refuses
- [x] Unit tests for imbalance / spread filters

## Phase 1 — Read loop (paper marks)

- Poll HL public `/info` `l2Book` for BTC/ETH/SOL/HYPE (same universe as Rail)
- Emit `Signal` when imbalance ≥ threshold and spread ≤ cap
- Paper simulator: marketable limit at mid ± half-spread, fee model, latency fill delay
- Local JSONL journal: signal → fill → exit → PnL
- CLI: `python -m hl_scalper.loop --mode paper`

Success: overnight paper run with stable journal and no crashes on empty books.

## Phase 2 — WS + scalp exits

- Hyperliquid websocket book stream (sub-second updates)
- Hold time budget (e.g. 2–30s) + adverse-selection exit (imbalance flip / mid move)
- Maker-prefer path when spread allows; else take and demand larger edge
- Fee + funding awareness on hold (even short holds accrue funding on HL)

Success: paper Sharpe / expectancy report over ≥7 days of journal; sit-out rate logged.

## Phase 3 — Risk hardening

- Hard caps: notional, leverage, open positions, daily loss, consecutive losses
- Kill switch + cooldown; manual arm file required to resume
- Stale-book / clock-skew / HTTP error tripwires
- Replay harness: recorded books → deterministic PnL

Success: kill switch unit + integration tests; replay matches journal within tolerance.

## Phase 4 — Tiny live (separate process only)

- Agent wallet signing **outside** Signal Engine deploy
- Same strategy code path as paper (`--mode live` behind `LIVE_ENABLED` + arm file)
- Start at dust size; promote size only after paper expectancy stays positive

Success: live fills reconcile to HL user state; SE/Rail production untouched.

---

## Non-goals (v0–v2)

- Cross-venue arb (Binance signal → HL fill)
- Equity / Alpaca / Robinhood
- LLM order decisions
- Coupling into SE Celery or `/rail` clerk UI
- HIP-4 outcomes (later; not scalp core)

---

## Edge hypothesis (to falsify)

When top-of-book notional is heavily skewed (≥ ~72% one side) and spread is tight
(≤ ~12 bps), short-horizon mid moves in the heavy direction more often than fees
+ adverse selection cost. If paper journals falsify this after Phase 2, retire or
retarget (queue fade / funding only) — do not “force” live.

Rail’s `scanners/book.py` is the starting threshold set; this lab may tune freely
without changing Rail production scanners.
