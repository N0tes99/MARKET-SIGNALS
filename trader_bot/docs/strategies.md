# Strategies in place

All paths are **Hyperliquid perps** oriented. Taker path uses **IOC** economics;
S2 maker uses **paper post-only** resting quotes (live ALO deferred).

## Active strategies

| ID | Name | When active | What it does |
|----|------|-------------|--------------|
| `imbalance` | **S1** L2 book imbalance | Always (solo default) | Taker enter when skew ≥ 0.72 / ≤ 0.28 and spread ≤ 12 bps |
| `maker` | **S2** post-only join | `--maker` / `HL_MAKER=true` | Rest join bid/ask on mild lean; cancel on adverse/cross; fill on touch |
| `funding` | **S3-lite** funding lean | `--ensemble` only | Enter against rich/cheap funding extremes |
| `liquidity` | Liquidity / depth gate | `--ensemble` only | Sit out on thin/wide books; soft lean at 0.60/0.40 imb |
| `spread_micro` | **S2-lite** tight spread vote | `--ensemble` only | Vote-only tight-spread lean (does not rest quotes) |
| `risk` | Risk gate | Always | Kill / cooldown / stale / fee·edge veto |

### Solo modes
- Default: S1 taker `evaluate()` → RiskGate → IOC executor  
- `--maker`: S2 maker `evaluate_maker()` → RiskGate → paper resting quote  

### Ensemble mode (`--ensemble`)
Specialists vote → coordinator (min 2 agree) → RiskGate → executor.  
With `--maker`, `MakerAgent` joins the ballot; if its maker `Signal` wins, paper rests a quote instead of IOC.

```bash
# S2 maker paper only
python -m hl_scalper.loop --mode paper --maker --coins BTC,ETH --data-dir data

# Ensemble + maker specialist
python -m hl_scalper.loop --mode paper --ensemble --maker --coins BTC,ETH --data-dir data
```

## Exits (all modes)
- Hold time (`hold_seconds`, default 5s)
- Adverse mid (`adverse_exit_bps`, default 8)
- Imbalance flip  
Flatten still uses **taker IOC** economics (urgent exit).

## HL-realistic economics
### Taker (S1)
- Entry/exit limit: mid ± `max(spread, ioc_slip_bps_min)` (min **5 bps**)
- Fees: `taker_fee_bps` both sides (**3.5**)
- Live: parse IOC `avgPx` / `totalSz`

### Maker (S2 paper)
- Join best bid/ask (post-only; never cross)
- Fee: `maker_fee_bps` (default **1.0**, conservative vs rebate)
- Cancel: adverse mid / would-cross / off-touch (`maker_cancel_bps`)
- Fill: when touch trades to resting price
- **Live ALO posts: not enabled yet** (`maker_live_scaffold_paper_only`)

## Not built yet
- Live ALO / post-only on HL `/exchange`
- Two-sided simultaneous quotes + inventory skew controller
- True maker rebate tier from account fees
- Funding carry PnL on holds
