# Paper book → execution → first live test (parked build)

> **Status:** Diagnosis + plan. **Do not start Hyperliquid Phase C or live options.**
> **Snapshot:** production public preview, 2026-08-28 23:08 UTC
> **Last updated:** 2026-08-28

The public paper bot has **enough closed trades to start slicing execution**, not
enough of a *single* edge to go live. Hyperliquid and listed options are both
real later lanes. Neither is ready this week.

---

## 1. What the book says (honest vs optimistic)

Production `GET /api/v1/public/preview` (ledgers only; no per-trade dump without admin CSV):

| Ledger | Closed | W / L | Equity | Realized | Open | Return |
|--------|--------|-------|--------|----------|------|--------|
| Honest (next 15m open) | 41 | 18 / 23 | $15,096 | **+$15** | 4 | **+0.64%** |
| Optimistic (signal last) | 44 | 17 / 27 | $14,671 | −$403 | 6 | −2.19% |

Starting cash $15k, $2,500/name, daily cap 5. Honest win rate **43.9%**.
Density gate in `maturity.py` is 30 honest closes — **count is met**. Realized
edge is a rounding error (~0.01% per closed name). Optimistic is the worse
book, so **fill lag is already costing more than the signal**.

`last_tick_at` was **16:52 UTC** (~6h before this snapshot). Stops and honest
fills cannot fire while the bot is asleep. That is an execution bug, not an
alpha bug.

We could not slice by `source` / `setup_type` / `close_reason` from here
(admin `GET /api/v1/paper/trades.csv`). The CSV also omits `source` and
`close_reason`, so even a dump is thin for win-rate work.

---

## 2. Logic the bot already has (mixed book)

One agent, several idea factories, one $2.5k sleeve:

| Source | What it actually fills | Confirm |
|--------|------------------------|---------|
| `crypto_setup` | Spot/perp mark as a dollar sleeve | Grade ≥ B, F&G, ATR SL/TP |
| `crypto_perp_v2` | Same | Plus crowded-funding skip; expansion defer |
| `squeeze_expansion` | Same | ATR only (no F&G / grade) |
| `equity_setup` | **The stock**, not the option | Grade, earnings ≤2d, cash session |
| `tape_hunt` | **The stock** | Same confirm + hot tape only |
| `cme_futures` | Yahoo continuous future | ATR, no F&G |

Exits: ATR (or 6/3 fallback), **72h max hold**, 5 bps slip, no trail, no partials,
flat size. Rail clerk `paper_ack` is **not** a second PnL book.

So: we have enough *rows* to improve **this** bot’s execution. We do **not**
have a Hyperliquid paper ledger or an options-premium ledger.

---

## 3. Execution work that can raise win rate (paper, first)

Do these before any live venue:

1. **Richer export** — add `source`, `close_reason`, `direction`, hold hours to
   `paper/trades.csv` (keep the existing columns). Then dump production and
   slice W/L by setup and by `take_profit` vs `stop_loss` vs `max_hold`.
2. **Fix tick freshness** — if `last_tick_at` is hours stale, max-hold and stops
   are fiction. Keep-warm paper-first (PR #100) must stay green.
3. **One-source A/B** — freeze daily cap on the worst source after the slice
   (likely equity-as-stock or max-hold scratches). Do not retune all knobs at once.
4. **Exit experiment** — trail after +1R or flatten at 24h if `max_hold_72h`
   dominates losers. Policy snapshot already hashes knobs for replay.
5. **Do not** treat 44% WR as a reason to widen size.

Crypto learn already waits for 30 `perp_momentum` honest rows before applying
coefficients. Do not mix that with equity/tape/CME when judging a live test.

---

## 4. Live-test lanes (pick later, not now)

| Lane | Ready? | Why |
|------|--------|-----|
| **Hyperliquid Rail Phase C** | **No** | Live adapters refuse by design. Clerk paper is ack-only, no PnL. Plan already says: do not start C until *Rail’s* paper book has a sample, in a **separate process**, no keys on Render. |
| **Listed options** | **No** | Scanner + plan exist; paper fills the **underlying**. Theta, spread, and DTE are untested. Robinhood Agentic `place_option_order` is user-MCP only (`docs/research/robinhood-agentic-mcp.md`). |
| **SE paper, crypto-only** | **Yes (now)** | Honest book is the proof track. Tighten execution here. |
| **Alpaca** | Read-only mirror | Still no place/cancel. Leave it. |

**If we later pick Hyperliquid:** tiny size, agent wallet off Render, Rail
envelopes only (not desk 13-category grades), after a Rail paper PnL track
exists. That is still Phase C in `docs/research/rail-execution-surface.md`.

**If we later pick options:** first paper the *contract* (premium, bid/ask,
DTE harvest from `plan_builder.py`), then a tiny live test in a user session
(Alpaca/RH), never from keep-warm.

Default this month: **paper execution**, not a live venue.

---

## 5. Explicitly out of scope until status changes

- `place_*` on Render, Celery, or GitHub keep-warm
- HL `/exchange`, agent wallets on the API host
- Treating optimistic PnL as a live signal
- Skipping the CSV slice “because 41 closes feels like enough”
