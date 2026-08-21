# Brain + Expansion Engine — Directory Map

Living layout for Surface 5 (expansion radar) and the cortex brain.
**Implemented** modules run today; **scaffold** folders are reserved for the next phases.

```
backend/app/
├── cortex/                          # Brain — orchestration (Phase B ✅)
│   ├── orchestrator.py              # Heartbeat tick
│   ├── types.py                     # WorkingMemory, SpecialistOpinion
│   ├── attention.py                 # Which specialists fire
│   ├── specialists.py               # expansion, regime, derivatives, CVD proxy, news, macro
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
│   └── procedural/                  # How to behave (still config-backed)
│       └── config_store.py
│
├── data_lake/                       # Historical senses (still scaffold)
│   ├── schemas.py                   # Normalized bar/snapshot types
│   ├── ingest/                      # Backfill jobs
│   ├── warehouse/                   # Postgres / parquet storage
│   └── replay/                      # Point-in-time rewind (feeds expansion replay)
│
├── engines/
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
│       └── scoring/                 # Composer / weights (still scaffold)
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

## Phase B notes

- CVD specialist is an **OHLCV buying-pressure proxy**, not exchange-tape cumulative volume delta.
- News specialist is the **macro/event calendar** (FRED when keyed), not a headline NLP feed.
- Macro is a **global** opinion once per tick.
- Run `alembic upgrade head` so `cortex_episodes` / `cortex_semantic_stats` exist; otherwise the factory stays in-memory.
