# Multi-agent execution desk

Status: **implemented** (paper / dry-run live)  
Goal: better execution by **not relying on a single strategy agent**.

---

## Why

Wallet research showed winners run **systems** (cadence, balance, risk), not one finger.
A solo imbalance scalp will overtrade noise. The desk forces specialists to agree
— disagreement is a first-class **sit out**.

---

## Agents

| Agent | Role | Vote styles |
|-------|------|-------------|
| `imbalance` | S1 L2 book imbalance | enter / abstain |
| `funding` | S3-lite HL funding extreme | enter / abstain |
| `liquidity` | Quality gate (spread/depth) | enter lean / sit_out / abstain |
| `spread_micro` | S2-lite tight-spread micro lean | enter / abstain |
| `risk` | Hard veto via `RiskGate` | veto (post-ensemble) |

```
Books + funding ctx
        │
        ▼
 ┌──────────────┐
 │ Specialists  │  each emits Proposal
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │ Coordinator  │  veto/sit_out/disagree → flat
 │ min_agree=2  │  same-side agreement → candidate
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │ RiskGate     │  final veto
 └──────┬───────┘
        ▼
   Executor (paper / dry-run live)
```

## Coordinator rules

1. Any `veto` → sit out  
2. Any explicit `sit_out` → sit out  
3. Opposing `enter` sides → sit out (never average)  
4. Need `ensemble_min_agree` (default **2**) on the same side  
5. Risk gate runs last and can still kill the trade  

## Run

```bash
cd trader_bot
python -m hl_scalper.loop --mode paper --ensemble --coins BTC,ETH --data-dir data
# or: HL_ENSEMBLE=true

# optional CRT desk (same data-dir)
python -m hl_scalper.webapp --data-dir data --port 8787
```

Journal events: `ensemble` (full ballot + optional `signal` snapshot) → `signal` / `sit_out` → `fill`.

## Tunables (`Settings`)

| Knob | Default | Meaning |
|------|---------|---------|
| `ensemble` | false | Enable desk |
| `ensemble_min_agree` | 2 | Minimum same-side enters |
| `funding_extreme` | 1e-4 | Funding vote threshold |
| `spread_micro_tight_bps` | 4 | Spread-micro tight gate |

## Non-goals (yet)

- LLM agents deciding size  
- Copy-trading other wallets as agents  
- Parallel conflicting positions (still max 1 open)
