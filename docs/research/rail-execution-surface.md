# Surface 6 — Rail (blind crypto execution clerk)

> **Status:** Phase A scaffold (paper-only). Live venues are stubs that cannot place orders.
> **Decision:** Nested site at `/rail`, not a separate repo — yet. Extract when real money exists.

This is the plan for an agent that **sees opportunity and knows how to execute**, without
reading the thesis. Signal Engine stays the research desk. Rail is the clerk.

---

## 1. Should this be a separate product?

**Build it as a site-within-the-site now. Split the process later.**

| Option | When it wins | Cost |
|--------|----------------|------|
| Separate repo / deploy | Live keys, SOC-ish isolation, different SLA | Duplicates auth, wallets, evidence, scanners |
| Nested `/rail` (chosen) | Same edge, same login, one deploy, fast iteration | Must firewall keys and UX so the desk does not become a casino |
| Separate later | After paper maturity + first live venue | Move `backend/app/engines/rail/` + `/rail` UI; keep envelope schema |

Signal Engine already has the **edge**: crypto perp v2, expansion radar, dual-ledger paper
agent, funding/OI, Fear & Greed, wallet login (ETH / Solana / Sui). Building a second
product that re-discovers “when to trade” would throw that away.

The product philosophy still holds for Surfaces 1–5: **Signal Engine is not a trading bot.**
Rail is a *different* surface. It is allowed to execute **only** through a sealed envelope
and a kill switch. Engines never call a venue. The clerk never calls an engine.

**Extract trigger (do not wait for a calendar):** first time a signing key or agent wallet
would live in this API process. Then Rail becomes its own worker with no intelligence
code on the same host.

Railway.app is **not** this surface. Production stays Render + Netlify (`docs/deploy.md`).
“Rail” means on-chain execution rails.

---

## 2. What the agent is (and is not)

The request: *it does not see what the trade consists of, but it sees opportunity and
knows how to execute like a human, faster.*

That is an **order clerk**, not an LLM trader.

```
Desk (Signal Engine)                         Clerk (Rail)
────────────────────                         ────────────
Sees symbol, thesis, factors, prices         Sees side, size band, urgency, edge, TTL
Ranks opportunity                            Does not know BTC vs SOL vs a Polymarket slug
AI Analyst explains                          Venue adapter knows HOW to send/cancel/manage
Never holds signing keys                     Never reads evidence or chart screenshots
```

A human scalp trader does the same split: research on one screen, finger-memory on the
other. Rail is the finger-memory, automated.

**Not in scope**

- An LLM that “looks at the chart and decides”
- YOLO sizing, martingale, copy-trading
- Custody of user funds on the API host
- Public live bot in Phase A

**In scope (Phase A)**

- Sealed `OpportunityEnvelope`
- Nested `/rail` clerk UI (blind)
- Paper venue that dry-runs fills from the existing paper agent book
- Catalog + hard-off stubs for Hyperliquid, Drift, Polymarket

---

## 3. Venue / chain choice (most open *for this job*)

“Most open-source chain” is the wrong first question. The first question is **where a
fast clerk can have an edge without KYC theater and with a real order API**.

| Venue | Chain | Market | Openness | Fit for *this* agent |
|-------|-------|--------|----------|----------------------|
| **Hyperliquid** | Own L1 (not Solana) | Perps CLOB | Matching + agent wallets; the current perp-bot default | **Primary live target.** Native perps, funding, HIP agent wallets. Our scanners already think in perps. |
| **Drift** | Solana | Perps | Fully OSS, permissionless | **Solana option** if we insist on SOL settlement. Slightly worse clerk fit (AMM/JIT vs pure CLOB). |
| **dYdX v4** | Cosmos | Perps | Fully decentralized | Strong OSS; extra chain ops. Not first. |
| **Polymarket** | Polygon | Prediction CLOB | Public CLOB + Gamma APIs | **Second market type**, not a perp substitute. Different edge (probability vs tape). |
| Binance/Bybit API | Off-chain | Perps | Closed, geo-blocked | We already *read* them. Do not *write* them from this product. |

**Recommendation**

1. **Keep using Signal Engine scanners** (Bybit/OKX/Kraken reads) for edge.
2. **Execute perps on Hyperliquid first** when (if) we go live — best clerk venue.
3. **Keep a Drift adapter** so Solana remains a first-class option, not a rewrite.
4. **Polymarket as a parallel market_kind=`prediction`**, same envelope, different adapter.
5. Do **not** start on Solana just to be on Solana. Start where the book we already
   score (crypto perp v2 + expansion) can be handed to a clerk.

Phase A executes nowhere live. The clerk’s `venue` is always `paper`. Each envelope
still carries a `target_venue` so the nested site shows where the same opportunity
*would* rail later.

---

## 4. Envelope contract (the firewall)

Clerk-facing JSON **must not** contain: symbol, factors, notes, prices, thesis, setup
type names that encode the asset.

```
envelope_id          paper:{trade_id}     stable
venue                paper                where the clerk may fill now
target_venue         hyperliquid|drift|polymarket
market_kind          perp | prediction
side                 buy | sell
size_band            xs | s | m | l       not notionals
urgency              passive | normal | aggressive
edge_score           0–100                no “why”
ttl_seconds          int
invalidation         stop_band_{1-9}      not a price
instrument_handle    hmac hex             only adapters resolve it
status               open | closed
```

Resolution of `instrument_handle` → symbol lives **inside** the venue adapter, never in
the `/rail` payload. The desk (`/perps`, `/assets/{symbol}`) remains the place a human
inspects the thesis. Rail may link “inspect on desk” without showing the symbol on the
clerk card.

---

## 5. Process firewall

```
Evidence / Opportunity / Expansion / Paper Agent
        │  mint_envelope()  (strips thesis)
        ▼
OpportunityEnvelope  ──────────────────────────►  /rail UI (blind)
        │
        ▼
Rail Clerk  (kill switch + daily cap + size band)
        │
        ├── paper adapter      Phase A: dry-run ack only
        ├── hyperliquid        Phase A: hard refuse
        ├── drift              Phase A: hard refuse
        └── polymarket         Phase A: hard refuse
```

Rules:

- Engines never import a venue adapter.
- Venue adapters never import an engine.
- `RAIL_ARMED` and `RAIL_LIVE_ENABLED` default **false**.
- Phase A live adapters refuse even if those flags are flipped and even if keys exist.
- No signing keys in this repo or in `.env.example` (there isn’t one). Document names only.

Portfolio management is **Phase D**: one clerk, many envelopes, risk engine veto on
gross / per-venue / correlation. Do not build a “portfolio AI” first.

---

## 6. Nested site UX

| Route | Role |
|-------|------|
| `/` `/perps` `/expansion` | Desk — thesis, symbols, paper PnL |
| `/rail` | Clerk — opportunities as side / band / urgency / edge. Own chrome. |

`/rail` uses its own header (leave → Desk). Main nav still has a Rail link so it is
discoverable. This is a site-within-the-site: same auth, same CSP, different job.

---

## 7. Phases (technical, not calendar)

| Phase | Ship |
|-------|------|
| **A — this PR** | Envelope, clerk dry-run, paper venue, live stubs, `/rail`, docs |
| **B** | Read-only Hyperliquid/Drift/Polymarket mirrors (balances, positions). Still no orders. |
| **C** | Private micro-live, **separate process**, agent wallet, dual-control arming, after paper maturity gates already on the paper agent (`ready_for_private_live`) |
| **D** | Multi-venue portfolio: caps, correlation veto, shared kill switch |

Do not skip B. A clerk that cannot see its own inventory is how accounts blow up.

---

## 8. Risks

- **Product confusion:** desk users think Signal Engine now autotrades. Copy on `/rail`
  must say paper-only / not live.
- **Leakage:** one symbol in a clerk field undoes the design. Tests dump JSON and ban
  tracked symbols.
- **Live keys on Render:** forbidden until extract. This API already has Discord/Groq
  keys; adding a trading key is a different liability class.
- **Polymarket vs perps:** do not average those edges. Same clerk, different `market_kind`.
