# Strategies in place

All paths are **Hyperliquid perps** oriented. Execution is modeled as **taker IOC**
(same pricing/fee math for paper and live). Live posts still require arming +
`DRY_RUN_LIVE=false`.

## Active strategies

| ID | Name | When active | What it does |
|----|------|-------------|--------------|
| `imbalance` | **S1** L2 book imbalance | Always (solo default) | Enter when top-of-book notional skew ≥ 0.72 (or ≤ 0.28) and spread ≤ 12 bps |
| `funding` | **S3-lite** funding lean | `--ensemble` only | Enter against rich/cheap funding extremes |
| `liquidity` | Liquidity / depth gate | `--ensemble` only | Sit out on thin/wide books; soft lean at 0.60/0.40 imb |
| `spread_micro` | **S2-lite** tight spread | `--ensemble` only | Enter only when spread ≤ 4 bps and book leans |
| `risk` | Risk gate | Always | Kill / cooldown / stale / fee·IOC round-trip veto |

### Solo mode (default)
`evaluate()` → RiskGate → sizer → executor.

### Ensemble mode (`--ensemble`)
Specialists vote → coordinator (min 2 agree, disagreement sits out) → RiskGate veto → executor.

## Exits (all modes)
- Hold time (`hold_seconds`, default 5s)
- Adverse mid (`adverse_exit_bps`, default 8)
- Imbalance flip

## HL-realistic economics (paper + live)
- **Entry limit:** mid ± `max(spread, ioc_slip_bps_min)` (default min **5 bps**)
- **Exit limit:** mid ± `ioc_slip_bps_min` (5 bps)
- **Fees:** `taker_fee_bps` both sides (default **3.5**)
- **Buffer:** `fee_edge_buffer_bps` (default **2**)
- **Risk:** block if estimated IOC round-trip > budget **or** `edge_score` < round-trip bps
- **Live:** parse HL IOC fill `avgPx` / `totalSz`; refuse to book inventory on unfilled IOC
- **PnL:** from executor fill prices (not mid marks)

## Not built yet
- True maker / post-only (S2 full)
- Funding carry PnL on holds
- Exchange-reported fee tiers (assumes 3.5 bps until fill fee API wired)
