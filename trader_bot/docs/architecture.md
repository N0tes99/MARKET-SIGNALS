# Architecture — HL scalper loop

```
Hyperliquid /info (+ WS later)
        │
        ▼
   BookFeed (read-only)
        │
        ▼
 ImbalanceStrategy ──► Signal | sit_out
        │
        ▼
   RiskGate (caps, kill switch, stale book)
        │
        ▼
 ExecutionPort
   ├── PaperSim   (default)
   └── LiveHL     (always refuse until Phase 4)
        │
        ▼
   Journal (JSONL) + metrics
```

## Modules

| Package | Responsibility |
|---------|----------------|
| `feed` | Fetch/parse L2 books; never sign |
| `strategy` | Pure functions: imbalance, spread, signal |
| `risk` | Position / daily loss / kill switch |
| `execution` | Paper fills; live stub refuses |
| `sim` | Fee, slippage, latency models |
| `loop` | Orchestrates one tick / run |

## Risk defaults (starting points)

- Max concurrent positions: 1
- Max notional per trade: configurable (paper starts small)
- Daily loss kill: −2% of paper equity
- Book max age: 2s (WS) / 15s (poll) before sit-out
- Live: `live_enabled=False` always in config defaults

## Isolation rules

1. No imports from `app.*` (Signal Engine). Duplicate the small L2 parse we need.
2. No writes to SE Postgres. Journal is local files under `trader_bot/data/` (gitignored).
3. Live adapter must raise `LiveTradingDisabled` even if env is mis-set, until Phase 4
   explicitly flips a code-level allowlist **and** an arm file is present.
