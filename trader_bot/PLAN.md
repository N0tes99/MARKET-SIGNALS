# Plan — Hyperliquid book-imbalance scalper

Status: **Phase 1 code complete** (overnight paper validation still operator-side)  
Venue: Hyperliquid perps  
Edge: L2 book imbalance scalping  
Last updated: 2026-09-06

## Goal

Build a separate process that can **gradually compound** paper (then tiny live)
equity by harvesting short-lived L2 imbalances on Hyperliquid — with ruthless
risk gates so a bad day cannot erase the account.

Signal Engine stays the desk. This folder is the **execution lab**.

---

## Phase 0 — Scaffold (done)

- [x] Top-level `trader_bot/` only (no `backend/` / `frontend/` edits)
- [x] Architecture doc + module stubs
- [x] Paper sim types + imbalance signal (ported from Rail book scanner math)
- [x] Live venue stub that always refuses
- [x] Unit tests for imbalance / spread filters

## Phase 1 — Read loop (paper marks)

- [x] Poll HL public `/info` `l2Book` for BTC/ETH/SOL/HYPE
- [x] Emit `Signal` when imbalance ≥ threshold and spread ≤ cap
- [x] Paper simulator + timed mid exit (`hold_seconds`)
- [x] Crash-safe JSONL journal + heartbeat
- [x] Sizer (equity fraction + max notional)
- [x] Feed error budget → kill switch
- [x] Optional `--record-books` for later replay
- [x] systemd unit + runbook
- [ ] Overnight paper run validation (operator)

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

Hyperliquid wallet model (the important non-CEX detail):

- **Master wallet** — holds funds; **only** withdraw key; never on a bot host
- **Agent (API) wallet** — authorized by master to sign `/exchange` orders only
- **Dual-control arming** — `LIVE_ENABLED` + manual arm file + kill clear + approved agent

Also required for live: reconcile vs HL user state, idempotent client order ids,
supervisor on a private box (not Render). Full rail map:
[`docs/automation-rails.md`](docs/automation-rails.md).

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
