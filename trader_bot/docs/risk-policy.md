# Risk policy — lose little by design

Defaults for the HL scalper lab. Encode these in `Settings` / `RiskGate` before any live arming.

## Capital envelope

| Knob | Paper default | First live |
|------|---------------|------------|
| Bot equity at risk | $10,000 sim | Dust ($50–$200) |
| Max notional / trade | $100 | ≤ $25 |
| Max leverage | 1–2x | 1x |
| Max open positions | 1 | 1 |
| Coins | BTC, ETH, SOL, HYPE | BTC, ETH only |

## Loss budgets

| Limit | Trip action |
|-------|-------------|
| Per-trade stop (adverse mid) | Exit immediately |
| Daily loss −1% equity | Kill switch: flatten intent + refuse entries |
| Weekly loss −3% equity | Disable strategy until manual review |
| Consecutive losses ≥ 5 | Cooldown 30–60 min |
| Feed failures ≥ 10 | Kill switch |

## Entry quality (must all pass)

1. Book age ≤ max (poll 15s / WS 2s)
2. Spread ≤ 12 bps (tighten to 8 bps live)
3. Top-5 notional ≥ $50k (BTC/ETH)
4. Imbalance ≥ 0.72 (or sit out)
5. Round-trip fee + slip buffer cleared by edge score
6. Kill switch clear + (live) arm file present

## Exit quality

- Time stop: `hold_seconds` (paper 5s; scalp live 2–30s)
- Signal flip: imbalance reverses through mid band
- Hard adverse: mid moves against by N bps
- Never “hope” — no widen stop, no add

## Wallet / ops

- Master wallet: custody + withdraw only (offline)
- Agent wallet: signs `/exchange` only
- Dual arming: `LIVE_ENABLED` + `data/ARMED` + kill clear
- Reconcile local vs HL user state before every entry (Phase 4)
- Journal every boot/signal/fill/exit/kill for post-mortems

## Promotion ladder

```
paper S1 ≥7d expectancy > 0 after fees
    → paper size stress (2× notional still OK)
        → live dust 1x BTC/ETH only
            → raise size only after another ≥7d live green
```

Any kill trip or reconcile mismatch → drop one rung.
