# Plan — Hyperliquid book-imbalance scalper

Status: **Phase 2–3 scaffolding toward live** (signer not wired; paper is the product path)  
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

- [x] Hyperliquid websocket book stream (hybrid cache + HTTP fallback)
- [x] Hold time + adverse mid + imbalance-flip exits
- [x] Fee + buffer awareness in risk gate
- [x] Expectancy report CLI (`python -m hl_scalper.report`)

Success: paper journals report expectancy / sit-out / kills; WS books fresher than poll.

## Phase 3 — Risk hardening (toward live)

- [x] Dual-control arming (`LIVE_ENABLED` + `ALLOW_LIVE_ORDERS` + `data/ARMED` + agent/master env)
- [x] Refuse if master private key env is present
- [x] Reconcile stub vs HL `clearinghouseState` (flat check before live entries)
- [ ] Replay harness from recorded books
- [ ] Alert hook on kill

## Phase 4 — Tiny live (separate process only)

Hyperliquid wallet model:

- **Master wallet** — holds funds; **only** withdraw key; never on a bot host
- **Agent (API) wallet** — authorized by master to sign `/exchange` orders only
- **Dual-control arming** — env + arm file + kill clear + approved agent

Also required: signed `/exchange` client, cloid idempotency, dust size on BTC/ETH only.
`allow_live_orders` stays **false** until signer is wired and paper expectancy is green.

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

## Wallet research → strategy choices

See [`docs/research/profitable-wallets.md`](docs/research/profitable-wallets.md) and
[`docs/risk-policy.md`](docs/risk-policy.md).

HL leaderboard winners are mostly **high-turnover two-sided micro-edge** systems,
not heavy trend apes. We therefore:

- Keep **S1 imbalance scalp** as the only active strategy until paper proves edge
- Prefer liquid majors; sit out by default
- Enforce −1% daily kill, 1 position, low leverage, fee+buffer gate
- Defer copy-trading / meme concentration / high leverage forever for this lab
