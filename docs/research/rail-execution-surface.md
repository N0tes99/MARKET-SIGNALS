# Surface 6 — Rail Engine (venue-native discovery + same-rail execution)

> **Status:** Phase A clerk shell exists (paper-only). **This revision** is the plan for a
> **separate engine** that finds things Signal Engine does not see, on a rail where we
> can also execute.
> **Last updated:** 2026-08-21

Signal Engine stays the off-chain research desk. Rail is not “the paper agent with a
faster finger.” It is a **different sense**: venue-native books, funding, and outcome
markets that SE never reads.

---

## 1. Product split (revised)

| | Signal Engine (Surfaces 1–5) | Rail Engine (Surface 6) |
|--|------------------------------|-------------------------|
| Job | Evidence, explainability, CEX-aggregated tape | Identify **and** (later) execute on **one** crypto rail |
| Data | Bybit / OKX / Kraken / Yahoo, Coinglass overlay, F&G, Reddit | The venue’s own `/info` + L2 book + funding + outcomes |
| Finds | 13-category grades, funding_extreme, liq_flush, basis_rich, 12h perp momentum, expansion squeeze, equity options, CME, runners | Things those scanners cannot see (below) |
| Executes | Never (paper agent is a proof track, not a venue) | Same rail it scanned — or it does not scan that market |
| UI | Desk, Perps, Expansion, Radar | Nested `/rail` clerk (blind envelopes) |

**Rule:** if we cannot execute a market on that rail, Rail does not identify it.
No “spot an arb on Binance, fill on Hyperliquid” in v1 — that is a different product
(cross-venue basis) and needs two adapters plus latency we do not have.

Phase A code still *mints* envelopes from the public paper book so `/rail` is not empty.
That is a **temporary feed**. Phase B replaces it with Rail’s own scanners. Paper-agent
ideas must not be the long-term alpha.

Same repo for now (auth, CSP, deploy). **Separate engine module**
(`backend/app/engines/rail/`). Extract the **process** before any signing key.

Railway.app is unrelated. Production stays Render + Netlify.

---

## 2. Which rail? (identify **and** execute)

The rail has to do both jobs: public market data we can scan, and an order API / agent
wallet we can submit to later.

| Rail | Identify | Execute | Verdict |
|------|----------|---------|---------|
| **Hyperliquid** | `/info` (meta, `l2Book`, funding, `outcomeMeta`) + WS books. Perps, HIP-3 deployer perps, HIP-4 outcome contracts, spot — one engine. | Agent (API) wallet signs trades; master wallet holds funds and is the only withdraw key. Same account / margin for perps **and** HIP-4 outcomes (live May 2026). | **The rail.** Scan here, fill here. |
| Drift (Solana) | On-chain AMM/JIT perps | Yes, OSS | Backup if settlement *must* be SOL. Worse clerk fit. |
| Polymarket (Polygon) | Public CLOB + Gamma | Yes | **Not first.** HIP-4 already puts outcomes on the same HL rail as perps. Use Polymarket later only for books HL does not list. |
| Binance / Bybit write APIs | SE already *reads* these | KYC, geo-block, not self-custodied rails | Out. SE may keep reading them. Rail does not write them. |

**Decision:** Hyperliquid is the crypto rail. One L1 CLOB, one USDC/USDH account, perps +
event contracts. That is the only venue where “identify things SE is not” and “execute
in there” are the same system.

Solana is optional later (Drift), not the starting rail.

---

## 3. What Signal Engine already identifies (do not rebuild)

SE’s crypto surface, today:

| Source | What it sees | Data |
|--------|----------------|------|
| Derivatives engine | Funding, OI Δ, optional liquidations → 13-category grade | Bybit → OKX, Coinglass overlay |
| Layer 2 setups | `funding_extreme`, `liq_flush`, `basis_rich` | Same CEX derivatives + mark vs spot |
| Paper perp v2 | 12h momentum + funding tilt + F&G + Reddit | 16-symbol `PERP_V2_UNIVERSE` |
| Expansion / cortex | Compression → squeeze fuel → trigger | Same universe, 1h OHLCV |
| Macro / regime / chart vision | Off-chain context | FRED, F&G, screenshots |

Gaps are **not** “better RSI.” They are **venue-native** facts SE has no adapter for.

---

## 4. What Rail Engine identifies (SE cannot)

All of these are Hyperliquid-native. Scan and (later) fill on the same book.

| Family | Opportunity | Why SE misses it |
|--------|-------------|------------------|
| **A. Book microstructure** | L2 imbalance, spread blowout, thin-ask walk, queue fade | SE has no `l2Book`. It has candles + CEX funding. |
| **B. HL-native funding** | HL funding vs HL premium, not Bybit’s print | SE funding is Bybit/OKX. HL can diverge for hours. |
| **C. HIP-4 outcomes** | Binary/event mid ≠ 1.00 (YES+NO), stale vs underlying, daily BTC/ETH binaries | SE has no prediction surface. Macro engine does not price an event contract. |
| **D. Perp ↔ outcome** | Same-account hedge: HL BTC perp vs HIP-4 “BTC above X by expiry” | Only exists on a rail that lists both. SE cannot even see the outcome leg. |
| **E. HIP-3 listings** | New `xyz:` deployer perps, auction/open interest ignition | SE universe is 16 CEX tickers. |
| **F. Liquidation / ADL tape** | HL-native liq map, not Coinglass aggregates | Different venue, different cascade. |
| **G. Inventory / basis on-rail** | Mark vs oracle, USDC/USDH spot vs perp on HL | SE `basis_rich` is CEX mark vs Yahoo/Kraken spot. |

**Phase B ships A + B + C only.** D–G after those prove they are not just noise.

Explicit non-goals (leave to SE or never):

- 13-category grades, equity options, CME, Reddit narrative
- LLM “looks at the chart and decides”
- Cross-CEX arb that we cannot fill on HL
- Polymarket as a first scanner (no HL fill path for those books)

---

## 5. Engine shape (still blind at the clerk)

```
Hyperliquid /info + WS          Signal Engine desk (optional overlay, never required)
        │
        ▼
Rail scanners (A/B/C)  —  see the full book / funding / outcome
        │  mint_envelope() strips ticker, prices, thesis
        ▼
OpportunityEnvelope (clerk-visible)
        │
        ▼
Rail Clerk + kill switch
        ├── paper         always allowed in Phase A/B (dry-run)
        └── hyperliquid   Phase C+ only, separate process, agent wallet
```

- Scanners **may** see symbol, book, mids. They live in `engines/rail/scanners/`.
- Clerk **may not**. `/rail` UI stays blind. “Inspect on desk” can deep-link to
  `/perps` or a future `/rail/inspect` that is **off** the clerk path.
- Rail scanners **do not** register with the Evidence Engine. They do not move
  BTC’s 13-category grade. Sitting out is valid.
- Execution still: engines never call `/exchange`; only the clerk does, and Phase A/B
  live adapters keep hard-refusing.

Envelope `market_kind` grows: `perp | outcome` (HIP-4). `prediction` stays as a
reserved id for a future Polymarket adapter — unused until we have a fill path.

---

## 6. Phases

| Phase | Ship | Execute? |
|-------|------|----------|
| **A** (in repo) | Clerk shell, paper dry-run, live stubs, `/rail` | Paper ack only |
| **B** (next build) | HL **read-only** adapter: `l2Book`, funding, `outcomeMeta`. Scanners A/B/C mint envelopes. Paper still the only fill. | No live orders |
| **C** | Private micro-live, **separate process**, HL agent wallet, dual-control arming, after paper maturity + B paper track on *Rail* ideas (not SE ideas) | HL only, tiny size |
| **D** | Perp↔outcome inventory, HIP-3, portfolio caps | Still HL-first |

Do not skip B. A clerk that cannot see HL inventory is how accounts blow up.
Do not start C until Rail’s own (not SE’s) paper book has a sample.

---

## 7. Risks

- **Product confusion:** `/rail` must say “HL-native scanner / not the desk grade.”
- **Leakage:** scanner logs can hold symbols; clerk JSON cannot. Keep tests.
- **Copying SE:** if a scanner is just Bybit funding under a new name, delete it.
- **HIP-4 liquidity:** many outcomes are thin. Size bands stay tiny; sit out is the default.
- **Keys:** agent wallet is still a live key. It never lands on the Render API host.

---

## 8. What Phase B would add (not built in this revision)

```
backend/app/engines/rail/
├── scanners/
│   ├── book.py          # A — L2 imbalance / spread
│   ├── funding.py       # B — HL funding vs premium
│   └── outcome.py       # C — HIP-4 YES+NO, stale vs underlying
├── adapters/
│   └── hyperliquid_info.py   # read-only POST /info
└── (existing clerk, envelope, paper venue, live refuse stubs)
```

`GET /api/v1/rail/desk` sources envelopes from these scanners, not from
`PaperAgent.summary()`. Paper agent remains the public proof track on the **desk**.
