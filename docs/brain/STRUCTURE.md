# Brain + Expansion Engine — Directory Map

Living layout for Surface 5 (expansion radar) and the cortex brain.
**Implemented** modules run today; **scaffold** folders are reserved for the next phases.

```
backend/app/
├── cortex/                          # Brain — orchestration (Phase B ✅)
│   ├── orchestrator.py              # Heartbeat tick
│   ├── types.py                     # WorkingMemory, SpecialistOpinion
│   ├── attention.py                 # Which specialists fire
│   ├── specialists.py               # expansion, regime, derivatives, tape CVD, news, macro
│   ├── synthesis.py                 # Cross-specialist notes + alerts
│   └── lifecycle.py                 # Health / stale ticks
│
├── memory/                          # Persistent knowledge
│   ├── protocols.py                 # MemoryReader / MemoryWriter
│   ├── episodic/                    # What happened ✅
│   │   ├── store.py                 # In-memory ring buffer
│   │   ├── postgres.py              # cortex_episodes
│   │   ├── factory.py               # SIGNAL_STORE auto / memory
│   │   └── types.py
│   ├── semantic/                    # What it means ✅
│   │   ├── consolidator.py          # primed → trigger lead time + calibration
│   │   ├── calibration.py
│   │   ├── lead_time.py
│   │   ├── store.py
│   │   ├── postgres.py
│   │   ├── factory.py
│   │   └── types.py
│   └── procedural/                  # How to behave ✅
│       └── config_store.py          # Postgres overlay; file defaults otherwise
│
├── data_lake/                       # Historical senses (write-through MVP)
│   ├── schemas.py                   # Normalized bar types
│   ├── ingest/                      # Live fetch → warehouse
│   ├── warehouse/                   # ohlcv_bars (+ in-memory fallback)
│   └── replay/                      # Warehouse rewind for expansion replay
│
├── engines/
│   ├── rail/                        # Surface 6 blind clerk (Phase A ✅ paper-only)
│   │   ├── types.py
│   │   ├── envelope.py              # Seals thesis → clerk primitives
│   │   ├── clerk.py
│   │   ├── desk.py
│   │   └── venues/                  # paper live; hyperliquid/drift/polymarket refuse
│   └── expansion_engine/            # Surface 5 specialists (MVP ✅)
│       ├── compression.py
│       ├── squeeze_fuel.py
│       ├── trigger.py
│       ├── state.py
│       ├── scanner.py
│       ├── replay.py                # Lead-time vs paper v2
│       ├── config.py
│       ├── types.py
│       ├── specialists/             # Package mirror (re-exports)
│       └── scoring/                 # Composer / weights ✅
│           ├── composer.py          # Named weights → up/down + Policy line
│           └── weights.py           # Normalize to 1.0; live policy provenance
│
├── tasks/
│   ├── cortex_tick.py               # Brain heartbeat ✅
│   └── memory_consolidation.py      # Every 6h + after each persist
│
└── benchmarks/
    └── pump_events.v1.yaml          # BTC / SOL / SUI labeled events ✅

frontend/app/
└── expansion/                       # Radar UI ✅ (blackboard + health + semantic)

frontend/components/
├── expansion-preview-strip.tsx      # Desk preview ✅
└── asset-expansion-card.tsx         # Asset detail (specialist notes, parallel to grades) ✅
```

## Paper bridge

`engines/paper_agent/squeeze_expansion.py` — consumes cortex **trigger/expansion** only (not PRIMED).

## API surfaces

| Route | Module |
|-------|--------|
| `/api/v1/expansion` | `api/routes/expansion.py` |
| `/api/v1/cortex` | `api/routes/cortex.py` |
| `/api/v1/cortex/semantic` | lead-time + calibration |
| `/api/v1/cortex/health` | tick freshness + store backend |
| `/api/v1/expansion/policy` | live knobs (file or Postgres) |
| `/api/v1/data-lake/ohlcv/{symbol}` | warehouse candles |
| `/api/v1/sse/dashboard` | live desk rankings (SSE) |

## Phase B/C notes

- CVD specialist prefers **Kraken (or Binance) public trades**; OHLCV buying-pressure proxy is the fallback.
- News specialist is the **macro/event calendar** (FRED when keyed), not a headline NLP feed.
- Macro is a **global** opinion once per tick.
- Expansion knobs live in `procedural_policies` when migrated; otherwise compiled defaults.
- Live fetches write 5m/15m/1h/4h/1d bars into `ohlcv_bars` (fail-open).
- Run `alembic upgrade head` so `cortex_episodes` / `cortex_semantic_stats` / `procedural_policies` / `ohlcv_bars` exist.
