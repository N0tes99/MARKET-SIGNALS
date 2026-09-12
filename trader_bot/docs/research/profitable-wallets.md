# Research — What profitable Hyperliquid wallets actually do

**Date:** 2026-09-06  
**Scope:** Public leaderboard study (43k addresses) + live `/info` samples  
**Goal:** Steal *process*, not trade copies — then hard-code loss caps into our bot.

---

## Sources

1. TechFlow / Minara: **43,618** HL leaderboard addresses → **12** high-score accounts  
   ([en article](https://www.techflowpost.com/en-US/article/33650))
2. Live HL `clearinghouseState` + `userFills` on those sample wallets (2026-09-06)
3. HL agent-wallet / bot risk practice (API wallet ≠ master withdraw key)

**Caveat:** All-time PnL ≠ forever skill. Fill snapshots ≠ full hedges.  
Use this for **risk + strategy selection**, not 1:1 copy trading.

---

## What the profitable cohort looks like

Of 12 filtered top accounts:

| Bucket | Count | Pattern | Profit logic |
|--------|------:|---------|--------------|
| High-turnover **two-sided** | 8 | ~49/51 buy/sell, huge notional, tiny edge | ~15–45 **bps on turnover**, repeated endlessly |
| Active day / ultra-short | 3 | Skewed one side, bursty PnL | Needs volatility; sampled windows often **ugly** |
| Heavy one-sided trend | 1 | Few trades, concentrated | Huge upside *and* ruin risk — minority |

**Modal winner is a system**, not “ape early”: cadence, buy/sell balance, size, market choice, turnover.

### Study addresses (public)

| Address | Style in study |
|---------|----------------|
| `0xe4c6ae25959d7fc66cf2dd5965fb78c5e09c4048` | Large two-sided; BTC-heavy depth |
| `0x523852be2db1a76a0e088ecbff32e849544054e5` (`perpfumbler`) | Same model across many markets |
| `0x399965e15d4e61ec3529cc98b7f7ebb93b733336` | Ultra-fast (~0.2s), near-perfect balance |
| `0x8c625ff57d8a4374784c7eff585dfdc42ccec974` | Day-trader; DOGE-concentrated |
| `0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66` | One-sided burst day-trade |
| `0xc926ddba8b7617dbc65712f20cf8e1b58b8598d3` | Small ticket / fast scalp style |
| `0x862dd8e68f30693e3d3c9daa42a440bc6d2a1f0c` | Heavy one-sided trend (rare) |

---

## What they are doing recently (live sample)

| Wallet | Snapshot | Recent flow |
|--------|----------|-------------|
| `perpfumbler` | ~$556k equity, ~$1.9M notional | Multi-name book; fills in **xyz oil/CL** + HYPE — still high turnover |
| Day-trade style (`0x77375a…`) | ~$1.7M equity, large majors open | High inventory; recent fill skew can be one-coin bursts |
| Small-ticket (`0xc926dd…`) | ~$140k, flat | Many small closes across alts — scalp ticket size |
| Trend (`0x862dd8…`) | ~$550k flat | BTC-heavy history; not always leveraged |
| Several MM-style study addrs | $0 equity this snapshot | Accounts rotate; fill tape still dense |

**For us:** winners stay busy on **liquid** flow, keep inventory managed, and repeat a micro-edge.  
Day-trader / trend samples can be rich all-time and still show ugly short windows — **do not size like them**.

---

## Strategy roster (loss-first)

### S0 — Do nothing (default)
Sit-out is a first-class action.

### S1 — Book imbalance scalp (only active lab strategy)
- Enter only if imbalance + tight spread + depth all pass  
- Hold seconds; exit on flip / time / adverse mid  
- Universe: **BTC/ETH** (SOL optional). No memes in v1.

### S2 — Maker / two-sided micro (Phase 2+)
Matches the 8/12 cohort better (rebates, inventory skew). Needs WS + cancel discipline.

### S3 — Funding harvest (optional later)
Only with hedge or dust size. Easy to blow up if treated as free yield.

### Avoid
- Copy-trading leaderboard wallets  
- DOGE-style single-asset day concentration  
- High leverage trend with large % of equity  

---

## Capital preservation (encoded)

Full table: [`../risk-policy.md`](../risk-policy.md)

Headline rules already moving into `RiskGate` / `Settings`:

- −1% daily kill, −3% weekly kill  
- Max 1 position, ≤2x leverage until proven  
- Fee + buffer gate (round-trip taker must still leave room)  
- Consecutive-loss cooldown  
- Live dust universe: BTC/ETH only  
- Agent wallet signs; master never on the bot host  
