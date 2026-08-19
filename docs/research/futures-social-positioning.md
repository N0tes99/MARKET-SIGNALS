# Futures “social” layer — positioning, not chat

> Status: Phase 1 overlay shipping (CFTC COT on `/futures` + CME paper skip). Do not fold into the 13-category grade.
> Related: `/futures` CME board, paper `cme_futures`, crypto Reddit confirmation.

---

## Verdict

Futures desks do not strengthen a thesis with WSB-style chat. They use **who is positioned**. The free, honest version of a social layer for CME is **CFTC Commitments of Traders** (weekly, public, no key). Reddit/X is a weak second for ES/CL/GC and should stay confirmation-only, like crypto Reddit today.

A long ES paper idea + leveraged-money net-short is **support**. The same idea + leveraged-money at a 3-year long extreme is **conflict**. That is the strengthen/weaken mechanic.

---

## What futures traders actually watch

| Source | Cadence | What it answers | Free? |
|--------|---------|-----------------|-------|
| CFTC COT / TFF / Disaggregated | Weekly (Fri, as-of Tue) | Who is long/short: commercials vs specs / leveraged funds | Yes — CFTC SODA |
| Open interest + volume | Intraday | Is the move attracting new risk or covering? | Partial (Yahoo OI is null on our board) |
| VIX / vol term structure | Intraday | Are ES longs paying for crash insurance? | Yahoo `^VIX` already in stack |
| Put/call, skew | Intraday | Options crowding | Usually paid / CBOE |
| Reddit / X / TradingView comments | Real-time | Retail narrative | Reddit OAuth we already have; X is not free |

NexusFi-style desks treat COT + OI + vol as sentiment. Chat is last.

---

## What we already have

- Crypto: Fear & Greed + Reddit confirmation (`sentiment_engine`, `reddit_public.py`). Subs are crypto/equity only — **no futures subreddits**.
- CME board: 12h/20d momentum, volume, Yahoo last. **`open_interest` stays null** (we dropped `ticker.info`).
- Paper CME: 3/day, ATR exits, extras include `oi` which is usually empty.
- `/social` is **our** user feed, not trader-positioning.

---

## Recommended layer (Phase 1)

**Name:** Futures positioning overlay (not a new Evidence category).

**Data:** CFTC Public Reporting SODA, no API key (optional app token later).

- Financials (ES, NQ, YM, RTY, ZN, ZB, ZF, 6E, 6J, 6B): TFF futures-only `gpe5-46if`
- Commodities (CL, NG, GC, SI, HG, ZC, ZS, ZW, …): Disaggregated futures-only `72hh-3qpy`

Live probe (18 Aug 2026): `GET .../gpe5-46if.json?cftc_contract_market_code=13874A` returned E-mini S&P as-of **2026-08-11**, OI **2,119,506**. Leveraged money **205,744 long / 486,190 short** (9.7% vs 22.9% of OI) — specs were **net short**, not chasing the index.

**Join key:** map `FUTURES_CONTRACTS` Yahoo roots → `cftc_contract_market_code` (e.g. `ES=F` → `13874A`, `CL=F` → `067651`, `GC=F` → `088691`).

**How it hits a thesis** (same pattern as crowded funding vs perp momentum):

| Paper / board direction | Specs (lev money / managed money) | Effect |
|-------------------------|-------------------------------------|--------|
| Long | Extreme net long (COT index ≥ ~80 or z ≥ +2) | **Weaken** — crowded chase |
| Long | Extreme net short | **Strengthen** — squeeze / catch-up fuel |
| Short | Extreme net short | **Weaken** |
| Short | Extreme net long | **Strengthen** |

Commercials / dealers on the other side of an extreme is extra confirmation, not a second score.

**Where it shows:** `/futures` row factors/conflicts + paper `cme_momentum` extras (`cot_index`, `lev_net`, `report_date`). Record in `policy.features` when paper opens. Do **not** retune 13-category weights from this.

**Honesty:** report is **stale by 3–6 days**. Label `as-of Tuesday`, never imply live positioning.

---

## What not to do first

- Scrape X/Twitter or TradingView comment sentiment (ToS / paid / noisy).
- Keyword-score r/wallstreetbets for `ES=F` as if it were BTC.
- Drive CME paper opens from COT alone (weekly data + 3/day cap = overfitting last Friday’s print).
- Treat AAII/NAAIM as per-contract (equity-wide only; optional later for ES only).

Reddit add-on (Phase 1b, optional): search `FuturesTrading`, `Commodities`, `thewallstreet` for CL/GC/ES aliases. Keep lean ±5 like crypto Reddit. Quiet → skip.

---

## CME OI gap

Yahoo continuous `=F` does not give usable open interest on our path. Weekly COT `open_interest_all` is a better **positioning** OI than a fake live OI. Do not pretend it is same-day CME pit OI.

---

## Open decisions

1. TFF leveraged-money vs asset-manager as the “spec” series for ES (desks usually watch **leveraged funds** for crowding).
2. 26-week vs 3-year COT index window.
3. Whether BTC=F/ETH=F use CME Bitcoin TFF row or stay on crypto funding (prefer **crypto funding** — that book is live; CME crypto COT is thin).
