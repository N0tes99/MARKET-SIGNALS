# Brain + Expansion Engine — Directory Map

Living layout for Surface 5 (expansion radar) and the cortex brain.  
**Implemented** modules run today; **scaffold** folders are reserved for the next phases.

```
backend/app/
├── cortex/                          # Brain — orchestration (Phase A ✅)
│   ├── orchestrator.py              # Heartbeat tick
│   ├── types.py                     # WorkingMemory, SpecialistOpinion
│   ├── attention.py                 # Which specialists fire
│   ├── specialists.py               # Adapters → regime, derivatives
│   ├── synthesis.py                 # Cross-specialist notes + alerts
│   └── lifecycle.py                 # Health / degrade (scaffold)
│
├── memory/                          # Persistent knowledge
│   ├── protocols.py                 # MemoryReader / MemoryWriter
│   ├── episodic/                    # What happened ✅
│   │   ├── store.py                 # In-memory ring buffer
│   │   └── types.py
│   ├── semantic/                    # What it means (Phase B scaffold)
│   │   ├── calibration.py
│   │   └── lead_time.py
│   └── procedural/                  # How to behave (Phase B scaffold)
│       └── config_store.py
│
├── data_lake/                       # Historical senses (Phase B scaffold)
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
│       └── scoring/                 # Composer / weights (Phase B scaffold)
│
├── tasks/
│   ├── cortex_tick.py               # Brain heartbeat ✅
│   └── memory_consolidation.py      # Weekly semantic update (scaffold)
│
└── benchmarks/
    └── pump_events.v1.yaml          # BTC / SOL / SUI labeled events ✅

frontend/app/
└── expansion/                       # Radar UI ✅ (api client + cortex blackboard)
    └── page.tsx

frontend/components/
├── expansion-preview-strip.tsx      # Desk preview ✅
└── asset-expansion-card.tsx         # Asset detail (parallel to grades) ✅
```

## Paper bridge

`engines/paper_agent/squeeze_expansion.py` — consumes cortex **trigger/expansion** only (not PRIMED).

## API surfaces

| Route | Module |
|-------|--------|
| `/api/v1/expansion` | `api/routes/expansion.py` |
| `/api/v1/cortex` | `api/routes/cortex.py` |
