# 10X Runner Detection Layer — Integration Plan

> Status: **Phase 4 v0** (lists + alert gates + stage rail; ignition/running may emit when Yahoo fundamentals exist; still preview, not orders. Paid SI and 8-K beat/guidance NLP still open; Phase 5 backtests not started).
> Related: `ARCHITECTURE.md` §5.5 (Surface 4), roadmap M10.
> Source brief: ChatGPT “10X Runner Detection Layer” spec (pasted 2026-08-12).

---

## Verdict

Build this as **Surface 4 — Runner Detection**, a parallel opportunity surface like Layer 3 equity options — **not** a new Evidence category and **not** a change to the 13-category grade path.

It consumes existing market/structure evidence where possible, adds fundamental/catalyst/discovery features the platform lacks today, and emits explainable `RunnerCandidate` objects + EARLY / IGNITION / RUNNING watchlists.

---

## 1. What already exists (reuse)

| Capability | Location | Reuse for Runner |
|------------|----------|------------------|
| OHLCV / ticker routing (Yahoo equities) | `market_data/service.py`, `providers/yahoo.py`, `providers/router.py` | Price, volume, dollar volume |
| EMA / ATR / HH-HL structure | `indicators/`, `utils/scoring_helpers.py` | MA structure, compression proxies |
| Equity momentum snapshot | `opportunity_engine/equity_options/momentum.py` | Relative volume, breakout proximity, structure score — **extract shared helpers** rather than duplicate |
| Sector / SPY relative strength | `engines/sector_rs_engine/` | Structure dimension + theme RS |
| Buyer/Seller / volume pressure | `engines/buyer_seller_engine/` | Accumulation proxy |
| Event / earnings calendar (slow path) | `engines/event_engine/` | Catalyst timing hooks (extend beyond “days to earnings”) |
| Risk evidence + veto patterns | `engines/risk_engine/` | Keep **Opportunity Score** and **Risk Score** separate |
| Evidence hub + DecisionPipeline | `evidence_engine/`, `services/decision_pipeline.py` | Optional *read* of category scores; **do not write** into grades |
| Setup scanner DI / TTL cache pattern | `opportunity_engine/scanner.py`, `equity_options/scanner.py`, `service_dependencies.py` | Same wiring pattern for `RunnerScanner` |
| Alerts (Discord/email + cooldown) | `services/alert_service.py`, `alert_state` | Threshold alerts for EARLY / high Runner Score |
| Learning + signal store | `learning_engine/` | Record runner signals + outcomes |
| Walk-forward backtesting skeleton | `backend/app/backtesting/` | Extend with lead-time metrics |
| Frontend feed pattern | equity-setups UI + `frontend/services/api.ts` | “10X Radar” page/section |
| Tracked symbol registry | `market_data/symbols.py` | Seed universe starts here; runner universe is **broader** and config-driven |

### Surfaces today

```
Surface 1 — Asset ranking          Evidence → grade → WAIT/WATCH/EXECUTE
Surface 2 — Crypto setups          funding / liq / basis
Surface 3 — Equity options         momentum / breakout + option plan
Surface 4 — Runner detection       NEW — fundamental inflection → ignition radar
```

Surface 4 **must not** alter Surfaces 1–3 scores. Same rule as Layer 3.

---

## 2. What is missing (new work)

These are the hard dependencies the current platform does not have:

| Gap | Needed for | Suggested approach |
|-----|------------|--------------------|
| Fundamental time series (revenue, EPS, margins, FCF, backlog/ARR/bookings) | Fundamental Score + acceleration | New provider(s): Yahoo fundamentals / SEC filings / paid (FMP, Polygon, etc.) behind a protocol |
| Estimate revisions & guidance changes | Fundamental + Catalyst | Same fundamentals provider or separate estimates feed |
| News / press / contract NLP classifiers | Catalyst Score | Pluggable `CatalystDetector` (start rule-based + keywords; later LLM classify) |
| Short interest, float, days-to-cover, borrow | Asymmetry + squeeze modifier | Short-interest provider (Finra / paid) |
| Institutional ownership changes | Discovery / Relative Discovery | 13F lag-aware provider; treat as delayed |
| Market cap / EV / cash / debt / dilution events | Asymmetry + risk flags | Fundamentals + corporate actions feed |
| Analyst coverage count / initiation | Discovery Gap | Estimates/coverage provider |
| Search / social / media attention | Relative Discovery | Reuse Reddit confirmation pattern; add Google Trends / news volume later — **confirmation, not thesis** |
| Theme / bottleneck graph | Theme + Bottleneck scores | Config YAML: themes → keywords → seed tickers → second-order map (not hardcoded “AI only”) |
| Historical multi-bagger study set | Backtest | Research dataset under `docs/research/` + `backend/app/backtesting/runners/` |
| Broad equity universe beyond `STOCK_SYMBOLS` | Discovery outside mega-caps | `RUNNER_UNIVERSE` config (seed list + eventual screener filters) |

**Important:** Without fundamentals, Phase 1–2 can only ship a **structure-only stub**. Do not claim Runner Score quality until Fundamental + Discovery Gap land.

---

## 3. Where the layer lives

```
backend/app/engines/runner_engine/
  __init__.py
  types.py              # RunnerStage, RunnerSignalType, RunnerCandidate, sub-scores
  config.py             # weights, thresholds, market-cap buckets (env/YAML)
  engine.py             # orchestrates scorers → RunnerCandidate
  scanner.py            # universe scan + EARLY/IGNITION/RUNNING lists
  scoring/
    fundamental.py
    catalyst.py
    structure.py        # wraps shared momentum/RS/volume helpers
    asymmetry.py
    discovery_gap.py
    theme.py
    modifiers.py        # short squeeze, institutional, penalties
  stage.py              # Stage 0–7 classifier
  explain.py            # factors / conflicts / risk flags
  providers/            # OR backend/app/market_data/providers/runner_*
    fundamentals.py     # protocol + stub/mock + first real adapter
    short_interest.py
    ownership.py
backend/app/schemas/runner.py
backend/app/api/routes/runners.py
backend/tests/test_runner_engine_*.py
frontend/ … 10X Radar UI
docs/research/runner-historical-study.md   # NBIS/SMCI/CRDO/… case notes
```

**Why not under `opportunity_engine/`?**  
Layer 3 is options-specific. Runner Detection is a full multi-scorer intelligence layer with its own data deps. Sibling engine (`runner_engine`) keeps boundaries clean; Opportunity Engine remains Surface 1 ranking only.

Optional later: thin re-export from `opportunity_engine` if we want one “ideas” aggregator API.

---

## 4. Integration with the existing pipeline

```
MarketDataService (+ new fundamentals/SI providers)
        │
        ├─► EvidenceEngine / DecisionPipeline     (unchanged)
        │
        └─► RunnerEngine.evaluate(symbol)
                ├─ read optional EvidenceBundle category scores (structure boost only)
                ├─ Fundamental / Catalyst / Structure / Asymmetry / Discovery Gap
                ├─ Theme / Bottleneck modifiers + risk penalties
                ├─ RUNNER_SCORE + RISK_SCORE (separate)
                ├─ Stage + SignalType
                └─ factors / conflicts (explainability)
                        │
                        ▼
              RunnerScanner → EARLY | IGNITION | RUNNING
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   /api/v1/runners   AlertService    LearningEngine
   10X Radar UI      (threshold)     (signal_records subtype)
```

### Design rules (align with platform principles)

1. **Evidence never predicts; AI never decides** — Runner Score is engine-computed; AI may narrate later.
2. **Opportunity Score ≠ Risk Score** — never suppress risk flags.
3. **Short interest is an accelerant**, never a thesis.
4. **Popularity is not bullish** — Relative Discovery rewards *rising institutional attention + still-low public awareness*.
5. **Optimize for inflection lead time**, not next-day alpha.
6. **Config over hardcoding** — weights, alert thresholds, cap buckets, theme graph.
7. **Degrade gracefully** — missing fundamentals → lower confidence / Stage capped / `data_quality` flag (same idea as Layer 3).

### Scoring shape (v1 formula)

Start multiplicative on four cores (as specified), then additive modifiers with clamps:

```
core = f(Fundamental) * f(Catalyst) * f(Structure) * f(Asymmetry)   # each f maps 0–100 → (0.2–1.2) or similar
RUNNER_SCORE = clamp(100 * normalize(core)
    + w_gap * DiscoveryGap
    + w_theme * ThemeBottleneck
    + w_inst * InstitutionalAccum
    + w_si * ShortSqueezePotential
    - penalties...)
```

Exact weight table lives in `runner_engine/config.py` and must be tunable for Phase 6. Log every component.

---

## 5. Files that will change (when implementing)

| File | Change |
|------|--------|
| `ARCHITECTURE.md` | §5.5 Surface 4 (done in plan PR) |
| `docs/roadmap/milestones.md` | M10 checklist |
| `backend/app/core/service_dependencies.py` | `get_runner_engine` / `get_runner_scanner` |
| `backend/app/api/router.py` (or equivalent) | Mount `/runners` |
| `backend/app/market_data/symbols.py` | Optional: do **not** dump seed list into global TRACKED; keep `RUNNER_SEED_UNIVERSE` in runner config |
| `backend/app/services/alert_service.py` | Runner threshold evaluators |
| `backend/app/engines/learning_engine/types.py` | Optional `signal_kind=runner` metadata |
| `frontend/services/api.ts` + new Radar page/components | 10X Radar UI |
| `docker-compose` / env docs | New API keys for fundamentals/SI if paid |

---

## 6. Phased build (smallest complete version first)

### Phase 1 — Data model + stub scanner (shippable skeleton)

- Types: `RunnerStage`, `RunnerSignalType`, `RunnerScores`, `RunnerCandidate`
- Config defaults (weights, alert thresholds, cap buckets)
- `RunnerEngine.evaluate` with **mock/stub** sub-scores + full explain schema
- API: `GET /api/v1/runners`, `GET /api/v1/runners/{symbol}`
- Unit tests on types, stage classifier stubs, config loading
- **No** dashboard polish yet beyond API

### Phase 2 — Structure + asymmetry from existing data (**done — preview**)

- Reuse Layer 3 momentum helpers + Sector RS + volume for **Market Structure Score**
- Yahoo `fast_info.market_cap` for **Asymmetry** (missing when cap absent)
- Seed universe scan without polluting Surface 1 `TRACKED_SYMBOLS` (Yahoo accepts ad-hoc 1–5 letter tickers)
- Compose uses **filled dimensions only**; structure-only Runner Score capped; ignition/running blocked
- Preview UI: `/radar` + home strip, labeled **Preview · structure only**. Missing dims render as em dash, not 50.

### Phase 3 — Fundamentals + catalyst + discovery gap

- Fundamentals provider protocol + first adapter
- Acceleration features (QoQ/YoY deltas of growth rates) — **v0:** QoQ revenue acceleration from Yahoo quarterly statements
- Catalyst overlay v0 (Yahoo earnings date + recent EDGAR 8-K/6-K count + Yahoo EPS surprise vs estimate). Beat/guidance NLP from 8-K text still open.
- `DISCOVERY_GAP_SCORE` = fundamental/catalyst change vs price/valuation expansion — **v0:** analyst/cap followership + PEG/P/S + 52-week expansion
- Institutional / SI providers as optional (degrade if missing)

### Phase 4 — Stages, alerts, 10X Radar UI (**v0**)

- Stage 0–7 classifier prioritizing Stages 1–4
- Signal types: EARLY_RUNNER, ACCUMULATION, IGNITION, CONFIRMED_RUNNER, EXTENDED_RUNNER, RUNNER_FAILURE
- Watchlists EARLY / IGNITION / RUNNING (may fill when Yahoo fundamentals exist; structure-only still capped)
- Alert gates per spec (early vs high-priority); Discord after silent baseline
- Dashboard “10X Radar” table + stage progression rail
- Separate Opportunity vs Risk columns

### Phase 5 — Historical backtest / lead time

- Labeled multi-bagger dataset (2×/3×/5×/10×) with point-in-time features at T-180…T0
- Metrics: precision/recall, false-positive rate, **lead time**, time-to-N×, max DD
- Strict no look-ahead (as-of dates on fundamentals/ownership)

### Phase 6 — Weight optimization

- Out-of-sample tuning; **do not** overfit famous winners
- Compare against Structure-only baseline

---

## 7. Seed universe & historical studies

**Seed list (testing / benchmarking only — not recommendations):**  
NBIS, CRWV, SMCI, IREN, AAOI, CRDO, ALAB, POET, INDI, COHR, LITE, MXL, AIP, ICHR, COHU, UCTT, AMPX, PLPC, PWR, CEG, VRT, CLS

**Pattern studies:** NBIS, SMCI, CRDO, ALAB, AAOI, LITE, CLS, VRT + other historical 5×/10× names.

Store case writeups under `docs/research/runner-case-studies/` when Phase 5 starts.

---

## 8. API sketch (Phase 1+)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/runners` | Ranked feed; filters: `list=early\|ignition\|running`, `min_score`, `stage` |
| `GET /api/v1/runners/{symbol}` | Full candidate + score breakdown + factors/conflicts/risks |
| `GET /api/v1/runners/meta/config` | Public thresholds (no secrets) |
| `POST /api/v1/runners/backtest` (later) | Kick or fetch lead-time study jobs |

Response always includes explainability fields — never bare “BUY / 87”.

---

## 9. Acceptance criteria for “smallest complete version”

1. Does not change Surface 1 grades or Layer 3 outputs (regression tests).
2. Returns at least one `RunnerCandidate` per seed symbol with logged component scores.
3. Missing data lowers confidence / sets `data_quality`, does not crash scan.
4. Opportunity and Risk scores are both present.
5. Architecture + this research doc stay in sync with code status.

---

## 10. Open decisions (resolve before Phase 3 coding)

1. **Fundamentals vendor:** free Yahoo snippets vs FMP/Polygon/SEC — cost vs point-in-time quality.
2. **Universe scope:** seed-only until screener filters (liquidity, listing, reporting quality) exist.
3. **Should Runner candidates appear on asset detail pages** alongside equity-setups? (Recommended: yes, read-only panel.)
4. **Paper agent:** auto-log EARLY→IGNITION transitions? Defer until Phase 4 stable.
5. **Crypto runners:** out of scope for M10 (equities first).

---

## Implementation instruction (for the coding agent later)

Follow `ARCHITECTURE.md` §18 checklist. Inspect reuse points above. Implement Phase 1 only in the first PR unless explicitly asked to go further. Preserve all existing functionality. Add tests + component-level logging + config. Document every new data dependency in this file and `ARCHITECTURE.md`.
