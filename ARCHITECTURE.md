# Signal Engine — Architecture

> **Living document.** Every major system is documented here *before* it is built. Update this file when adding, changing, or deprecating a component.

| Field | Value |
|-------|-------|
| Version | 0.3.0 |
| Last updated | 2026-08-02 |
| Status | Analysis engines live — decision pipeline pending |

---

## 1. Platform Purpose

Signal Engine is an **AI-powered Market Intelligence Platform**. It is **not** a trading bot.

Its purpose is to help traders make statistically superior decisions through **evidence accumulation**, not prediction. Think Bloomberg Terminal meets AI Analyst.

### Core Principles

| Principle | Meaning |
|-----------|---------|
| Protect capital first | Risk assessment precedes opportunity ranking |
| No trade is valid | Sitting out is a first-class decision |
| Evidence beats prediction | Weighted signals, not black-box forecasts |
| Explainability required | Every score must decompose into factors |
| Measurability required | Every feature has a metric |
| Backtestability required | Every signal and outcome is stored |
| AI explains, not decides | The AI Analyst narrates evidence; engines decide |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MARKET DATA LAYER                             │
│  Exchange APIs · Macro feeds · Derivatives feeds · Economic calendar   │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │ Trend Engine│         │Buyer/Seller │         │ Derivatives │
   │             │         │   Engine    │         │   Engine    │
   └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
          │                        │                        │
          │         ┌──────────────┴──────────────┐         │
          │         ▼                             ▼         │
          │   ┌───────────┐              ┌───────────┐      │
          │   │Macro Engine│              │  Regime   │      │
          │   └─────┬─────┘              │  Engine   │      │
          │         │                    └─────┬─────┘      │
          └─────────┼──────────────────────────┼─────────────┘
                    ▼                          │
          ┌─────────────────────┐              │
          │   EVIDENCE ENGINE   │◄─────────────┘
          │  (central hub —     │
          │   never predicts)   │
          └─────────┬───────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │ OPPORTUNITY ENGINE  │
          │  Rank · Grade · EV  │
          └─────────┬───────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │  EXECUTION ENGINE   │
          │ WAIT · WATCH · EXEC │
          └─────────┬───────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │    RISK ENGINE      │
          │ Size · Stop · TP · DD│
          └─────────┬───────────┘
                    │
          ┌─────────┴───────────┐
          ▼                     ▼
   ┌─────────────┐      ┌─────────────┐
   │ AI ANALYST  │      │  LEARNING   │
   │ (explains)  │      │   ENGINE    │
   └──────┬──────┘      └──────┬──────┘
          │                     │
          └──────────┬──────────┘
                     ▼
          ┌─────────────────────┐
          │  API + DASHBOARD    │
          │  WebSocket · REST   │
          └─────────────────────┘
                     │
                     ▼ (future)
          ┌─────────────────────┐
          │  BROKER ADAPTERS    │
          │  Read-only → Exec   │
          └─────────────────────┘
```

### Module Locations

| System | Path | Status |
|--------|------|--------|
| Evidence Engine | `backend/app/engines/evidence_engine/` | **Implemented** |
| Scoring | `backend/app/scoring/` | **Implemented** |
| Market Data | `backend/app/market_data/` | **Implemented** |
| Indicators | `backend/app/indicators/` | **Implemented** |
| Trend Engine | `backend/app/engines/trend_engine/` | **Implemented** |
| Buyer/Seller Engine | `backend/app/engines/buyer_seller_engine/` | **Implemented** |
| Derivatives Engine | `backend/app/engines/derivatives_engine/` | **Implemented** |
| Macro Engine | `backend/app/engines/macro_engine/` | **Implemented** |
| Regime Engine | `backend/app/engines/regime_engine/` | **Implemented** |
| Risk Engine | `backend/app/engines/risk_engine/` | **Implemented** (evidence only) |
| Opportunity Engine | `backend/app/engines/opportunity_engine/` | Placeholder |
| Execution Engine | `backend/app/engines/execution_engine/` | Placeholder |
| Learning Engine | `backend/app/engines/learning_engine/` | Placeholder |
| AI Analyst | `backend/app/engines/ai_engine/` | Placeholder |
| Backtesting | `backend/app/backtesting/` | Placeholder |
| Broker Adapters | `backend/app/adapters/brokers/` | **Not yet created** |

---

## 3. Evidence Engine

**Role:** Central hub. Collects evidence from all specialized engines. **Never predicts.**

### Responsibilities

- Invoke specialized engines for a given asset and timeframe
- Normalize each engine's output into a standard `EvidenceItem`
- Apply category weights to produce a `EvidenceBundle` with total confidence (0–100)
- Persist evidence snapshots for audit and backtesting
- Feed the Opportunity Engine

### Interface (planned)

```python
@dataclass
class EvidenceItem:
    source: str        # e.g. "trend_engine"
    category: str      # e.g. "Trend"
    score: float       # 0–100 within category
    weight: float      # category weight (e.g. 0.20)
    description: str   # human-readable factor

@dataclass
class EvidenceBundle:
    symbol: str
    timestamp: datetime
    items: list[EvidenceItem]
    total_confidence: float  # weighted sum, 0–100

class EvidenceEngine:
    def accumulate(self, symbol: str, timeframe: str) -> EvidenceBundle: ...
    def persist(self, bundle: EvidenceBundle) -> UUID: ...
```

### Design Rules

- No engine may bypass the Evidence Engine to reach the dashboard
- Weights are configurable but must always sum to 100
- Every `EvidenceItem` must include a `description` for AI Analyst consumption
- Evidence is immutable once persisted (append-only log)

### Dependencies

- All specialized engines
- Scoring module (`backend/app/scoring/`)
- PostgreSQL (evidence snapshots)
- Redis (latest bundle cache per symbol)

### Status

`IMPLEMENTED` — accumulation, scoring, persistence, and API live. Collectors return stub evidence until Milestone 3 engines are built.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/assets/{symbol}/evidence` | GET | Accumulate and return evidence bundle |
| `/api/v1/assets/{symbol}/evidence` | POST | Accumulate and persist snapshot |
| `/api/v1/assets/{symbol}/evidence/latest` | GET | Latest persisted snapshot |
| `/api/v1/evidence/snapshots/{id}` | GET | Snapshot by ID |

---

## 4. Specialized Analysis Engines

Each engine is an independent module with a single public method, strong typing, and unit tests. Engines produce **evidence**, not trade decisions.

---

### 4.1 Trend Engine

**Purpose:** Determine market direction.

| Output | Type | Description |
|--------|------|-------------|
| `direction` | `Bullish \| Neutral \| Bearish` | Primary trend classification |
| `confidence` | `float 0–100` | Strength of the trend signal |

**Inputs:** OHLCV candles, EMA, RSI, MACD (via `backend/app/indicators/`)

**Logic (planned):**
- Multi-timeframe trend alignment (e.g. 1h + 4h + 1d)
- EMA stack analysis (price vs 20/50/200 EMA)
- RSI divergence detection
- MACD crossover and histogram momentum

**Status:** `NOT IMPLEMENTED`

---

### 4.2 Buyer/Seller Engine

**Purpose:** Measure order flow dynamics.

| Output | Type | Description |
|--------|------|-------------|
| `buyer_strength` | `float 0–100` | Aggressive buying pressure |
| `seller_strength` | `float 0–100` | Aggressive selling pressure |
| `absorption` | `float 0–100` | Large orders absorbed without price move |
| `momentum` | `float 0–100` | Directional order flow momentum |

**Inputs:** Volume profile, trade tape, bid/ask depth (where available)

**Status:** `NOT IMPLEMENTED`

---

### 4.3 Derivatives Engine

**Purpose:** Analyze derivatives market positioning.

| Output | Type | Description |
|--------|------|-------------|
| `funding_rate` | `float` | Current perpetual funding rate |
| `open_interest` | `float` | Total open interest |
| `liquidations_24h` | `float` | 24h liquidation volume |
| `long_short_ratio` | `float` | Long/short positioning ratio |

**Inputs:** Exchange derivatives APIs, Coinglass or equivalent aggregator

**Status:** `NOT IMPLEMENTED`

---

### 4.4 Macro Engine

**Purpose:** Provide macroeconomic context that affects all assets.

| Output | Type | Description |
|--------|------|-------------|
| `dxy` | `float` | US Dollar Index |
| `treasury_10y` | `float` | 10-year Treasury yield |
| `fed_funds_rate` | `float` | Federal funds rate |
| `cpi_yoy` | `float` | CPI year-over-year |
| `unemployment_rate` | `float` | Unemployment rate |
| `upcoming_events` | `list[str]` | High-impact calendar events |

**Inputs:** FRED API, economic calendar feeds

**Status:** `NOT IMPLEMENTED`

---

### 4.5 Regime Engine

**Purpose:** Classify the current market environment.

| Output | Type | Description |
|--------|------|-------------|
| `regime` | `Trending \| Ranging \| Volatile \| Quiet` | Current regime |
| `confidence` | `float 0–100` | Classification confidence |

**Inputs:** ATR, Bollinger bandwidth, ADX, cross-asset correlation

**Logic (planned):**
- Regime affects weight adjustments in the Evidence Engine (e.g. reduce trend weight in ranging markets)
- Regime is global (not per-asset) but can have per-asset overrides

**Status:** `NOT IMPLEMENTED`

---

## 5. Decision Pipeline Engines

These engines consume evidence and produce actionable recommendations.

---

### 5.1 Opportunity Engine

**Purpose:** Rank every tracked asset by trade quality.

| Output | Type | Description |
|--------|------|-------------|
| `opportunity_score` | `float 0–100` | Composite score from evidence bundle |
| `trade_grade` | `A+ … F` | Letter grade mapped from score |
| `expected_value` | `float` | Estimated EV based on historical similar setups |
| `trade_state` | `IGNORE \| WATCH \| EXECUTE \| MANAGE \| EXIT` | Current state in state machine |

**Inputs:** `EvidenceBundle` from Evidence Engine, historical data from Learning Engine

**Grading scale (planned):**

| Grade | Score Range |
|-------|-------------|
| A+ | 90–100 |
| A | 80–89 |
| B | 70–79 |
| C | 60–69 |
| D | 50–59 |
| F | 0–49 |

**Status:** `NOT IMPLEMENTED` — REST placeholder at `GET /api/v1/opportunities`

---

### 5.2 Execution Engine

**Purpose:** Determine entry timing. Separates "good opportunity" from "good entry."

| Output | Type | Description |
|--------|------|-------------|
| `signal` | `WAIT \| WATCH \| EXECUTE` | Entry timing recommendation |
| `confidence` | `float 0–100` | Timing confidence |

**Logic (planned):**
- `WAIT` — Opportunity exists but conditions not yet aligned (e.g. waiting for pullback)
- `WATCH` — Key level approaching; alert user
- `EXECUTE` — Entry conditions met; hand off to Risk Engine

**Status:** `NOT IMPLEMENTED`

---

### 5.3 Risk Engine

**Purpose:** Calculate position sizing and risk parameters. **Always runs before any EXECUTE signal is surfaced.**

| Output | Type | Description |
|--------|------|-------------|
| `position_size` | `float` | Recommended position size in base currency |
| `stop_loss` | `float` | Stop loss price level |
| `take_profit` | `float` | Take profit price level |
| `max_drawdown` | `float` | Maximum acceptable drawdown for this trade |
| `risk_percent` | `float` | Percentage of account at risk |

**Inputs:** Evidence bundle, account balance, user risk profile, ATR for stop placement

**Design Rules:**
- Default max risk per trade: 1–2% of account (configurable)
- Stop loss always derived from structure (support/resistance) or ATR — never arbitrary
- Risk Engine can **veto** an EXECUTE signal if risk/reward is unfavorable
- Position size never exceeds user-defined maximum

**Status:** `NOT IMPLEMENTED`

---

## 6. AI Analyst

**Purpose:** Convert numerical evidence into human-readable reasoning. **Explains; does not decide.**

### Responsibilities

- Receive an `EvidenceBundle` and produce an `AIExplanation`
- Summarize top contributing factors in plain language
- Highlight conflicting signals (e.g. bullish trend but bearish funding)
- Never override engine outputs or generate trade signals independently

### Interface (planned)

```python
@dataclass
class AIExplanation:
    symbol: str
    summary: str           # 1–2 sentence overview
    confidence: float
    factors: list[str]     # bullet points
    conflicts: list[str]   # opposing signals flagged
    timestamp: datetime

class AIAnalyst:
    def explain(self, bundle: EvidenceBundle) -> AIExplanation: ...
```

### Example Output

> **Bitcoin scored 91** because:
> - Trend remains bullish across 1h and 4h timeframes
> - Volume expanded 40% above 20-period average
> - Funding normalized after elevated long positioning
> - Buyers defended $62,000 support three times
> - Risk/reward ratio 3.2:1 to nearest resistance
>
> **Conflict:** Macro headwind — DXY strengthening may cap upside.

### Technology

- OpenAI API (GPT-4 class model) for narrative generation
- Structured prompt with evidence bundle as JSON input
- Output validated against Pydantic schema before serving
- LangGraph integration planned for multi-step reasoning chains (future)

### Design Rules

- AI receives evidence; it never receives raw price data directly
- AI output is always labeled as "analysis" not "recommendation"
- Token usage tracked and metered per user (future)

### Status

`NOT IMPLEMENTED` — interface stub exists in `ai_engine/__init__.py`

---

## 7. Learning Engine

**Purpose:** Store every signal, trade, and outcome for future scoring weight optimization.

### Responsibilities

- Persist signal records with full evidence snapshot
- Record trade outcomes (win/loss/breakeven, PnL, duration)
- Provide historical query interface for backtesting
- (Future) Optimize scoring weights based on outcome data

### Data Model (planned)

```python
@dataclass
class SignalRecord:
    id: UUID
    symbol: str
    signal_type: str
    confidence: float
    evidence_snapshot_id: UUID
    trade_state: str
    timestamp: datetime
    outcome: str | None       # "win", "loss", "breakeven", "no_trade"
    pnl: float | None
    metadata: dict
```

### Design Rules

- Append-only — records are never modified, only outcome fields are updated
- Every signal links back to its evidence snapshot for full reproducibility
- Outcome tracking is optional (user may ignore signals without penalty)

### Status

`NOT IMPLEMENTED`

---

## 8. Scoring System

**Purpose:** Define how evidence categories combine into a total confidence score.

### Default Weights

| Category | Weight | Source Engine |
|----------|--------|---------------|
| Trend | 20 | Trend Engine |
| Momentum | 15 | Buyer/Seller Engine |
| Volume | 10 | Buyer/Seller Engine |
| Structure | 20 | Trend Engine |
| Risk | 15 | Risk Engine |
| Macro | 10 | Macro Engine |
| Derivatives | 10 | Derivatives Engine |
| **Total** | **100** | |

### Rules

- Weights are configurable per user tier (future) but must sum to 100
- Regime Engine can apply multipliers (e.g. 0.8× trend weight in ranging markets)
- Confidence recalculates every candle close for active timeframes
- Scoring logic lives in `backend/app/scoring/` — not inside individual engines

### Status

`NOT IMPLEMENTED` — module placeholder exists

---

## 9. Trade State Machine

Every asset progresses through a defined lifecycle:

```
IGNORE ──→ WATCH ──→ EXECUTE ──→ MANAGE ──→ EXIT
   ↑          │          │           │
   └──────────┴──────────┴───────────┘
              (conditions no longer met)
```

| State | Meaning | Trigger |
|-------|---------|---------|
| `IGNORE` | No actionable evidence | Score below threshold |
| `WATCH` | Evidence building; monitor | Score crosses watch threshold |
| `EXECUTE` | Entry conditions met | Execution Engine signal + Risk Engine approval |
| `MANAGE` | Active position tracking | User entered trade (manual or via broker adapter) |
| `EXIT` | Close recommended | Stop hit, target hit, or evidence reversal |

### Rules

- State transitions are logged by the Learning Engine
- Downgrade transitions (EXECUTE → WATCH) are as important as upgrades
- Dashboard displays current state per asset in real time via WebSocket

### Status

`NOT IMPLEMENTED` — enum defined in schemas only

---

## 10. Market Data Layer

**Purpose:** Ingest, normalize, and cache market data from external sources.

### Planned Structure

```
backend/app/market_data/
├── providers/          # Data source adapters
│   ├── base.py         # Abstract provider interface
│   ├── binance.py      # Binance REST + WebSocket
│   ├── coinbase.py     # Coinbase (future)
│   └── fred.py         # FRED macro data (future)
├── normalizer.py       # OHLCV normalization
├── cache.py            # Redis cache layer
└── scheduler.py        # Celery tasks for periodic ingestion
```

### Provider Interface (planned)

```python
class MarketDataProvider(Protocol):
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame: ...
    async def get_ticker(self, symbol: str) -> TickerSnapshot: ...
    async def subscribe_candles(self, symbol: str, timeframe: str, callback: Callable) -> None: ...
```

### Tracked Assets (v1)

BTC, ETH, SOL, SUI

### Design Rules

- All providers implement the same interface
- Data normalized to a standard OHLCV schema before reaching engines
- Stale data (> configurable threshold) triggers a degraded-mode flag, not silent failure
- Rate limiting and retry logic built into each provider

### Status

`NOT IMPLEMENTED` — module placeholder exists

---

## 11. Broker Adapters (Future)

**Purpose:** Connect to brokerage/exchange accounts for read-only portfolio data and (future) order execution.

> **Important:** Signal Engine v1 is intelligence-only. Broker adapters start as **read-only**. Execution requires explicit user opt-in and additional compliance review.

### Planned Structure

```
backend/app/adapters/brokers/
├── base.py             # Abstract broker adapter
├── read_only_mixin.py  # Shared read-only operations
├── binance.py          # Binance spot + futures
├── coinbase.py         # Coinbase Advanced Trade
├── alpaca.py           # Alpaca (equities, future)
└── paper.py            # Paper trading simulator
```

### Adapter Interface (planned)

```python
class BrokerAdapter(Protocol):
    # Read-only (v1)
    async def get_balances(self) -> list[Balance]: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_open_orders(self) -> list[Order]: ...

    # Execution (v2+, requires explicit enablement)
    async def place_order(self, order: OrderRequest) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> bool: ...
```

### Design Rules

- Read-only and execution capabilities are separate interfaces
- API keys stored encrypted; never logged
- Execution adapter requires Risk Engine approval on every order
- Paper trading adapter used for backtesting and demos
- Each adapter has its own rate limit and error handling
- Broker adapters are **never** called directly by engines — only by a dedicated Execution Service

### Status

`NOT STARTED` — directory does not exist yet

---

## 12. Backtesting Framework (Future)

**Purpose:** Replay historical evidence through the engine pipeline to validate scoring weights and strategy performance.

### Planned Capabilities

- Replay evidence accumulation over historical OHLCV
- Simulate state machine transitions without broker connection
- Compute performance metrics: win rate, avg R, max drawdown, Sharpe
- Compare scoring weight configurations side-by-side

### Location

`backend/app/backtesting/`

### Status

`NOT IMPLEMENTED` — module placeholder exists

---

## 13. API Layer

### REST Endpoints

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/health` | Service health check | **Live** |
| `GET` | `/api/v1/assets` | Dashboard asset summaries | Placeholder data |
| `GET` | `/api/v1/assets/{symbol}` | Single asset summary | Placeholder data |
| `GET` | `/api/v1/opportunities` | Ranked opportunities | Placeholder data |
| `GET` | `/api/v1/assets/{symbol}/evidence` | Full evidence bundle | Planned |
| `GET` | `/api/v1/assets/{symbol}/analysis` | AI explanation | Planned |
| `WS` | `/api/v1/ws/dashboard` | Real-time dashboard updates | Planned |

### Design Rules

- All endpoints versioned under `/api/v1/`
- Pydantic schemas for every request/response (`backend/app/schemas/`)
- Dependency injection for DB sessions (`backend/app/core/dependencies.py`)
- Rate limiting via Redis (future)

---

## 14. Frontend / Dashboard

### Pages

| Route | Purpose | Status |
|-------|---------|--------|
| `/` | Asset grid (BTC, ETH, SOL, SUI) | **Scaffolded** |
| `/assets/[symbol]` | Detail view with 9 analysis sections | **Scaffolded** (sections empty) |

### Detail View Sections (per asset)

1. Trend
2. Momentum
3. Volume
4. Market Structure
5. Funding
6. Macro
7. Risk
8. AI Explanation
9. Historical Similarity

### Technology

- Next.js 15 (App Router), React 19, TypeScript
- TailwindCSS + shadcn/ui (to be initialized)
- Recharts for charting
- TanStack Query for data fetching
- WebSocket hook for live updates (planned)

---

## 15. Infrastructure

### Services (Docker Compose)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | postgres:16-alpine | 5432 | Primary datastore |
| `redis` | redis:7-alpine | 6379 | Cache + Celery broker |
| `backend` | Custom (Python 3.12) | 8000 | FastAPI application |
| `celery-worker` | Custom (Python 3.12) | — | Background tasks |
| `frontend` | Custom (Node 20) | 3000 | Next.js dashboard |

### Background Tasks (Celery, planned)

- Periodic OHLCV ingestion
- Evidence recalculation on candle close
- Macro data refresh (daily)
- Derivatives snapshot (every 5 min)
- Stale data detection and alerting

### CI/CD (GitHub Actions)

- Backend: Ruff lint + Pytest with PostgreSQL/Redis services
- Frontend: ESLint + TypeScript check + production build

---

## 16. Data Storage (Planned)

### PostgreSQL Tables

| Table | Purpose |
|-------|---------|
| `evidence_snapshots` | Immutable evidence bundles |
| `signal_records` | Signals with outcomes (Learning Engine) |
| `market_candles` | Normalized OHLCV data |
| `macro_snapshots` | Periodic macro data |
| `derivatives_snapshots` | Periodic derivatives data |
| `user_preferences` | Risk profile, weight overrides (future) |

### Redis Keys

| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| `evidence:{symbol}:{timeframe}` | Latest evidence bundle | 5 min |
| `price:{symbol}` | Latest ticker | 30 sec |
| `regime:current` | Current market regime | 15 min |

---

## 17. Security Considerations (Planned)

- API keys (OpenAI, exchanges, brokers) stored in environment variables only
- Broker credentials encrypted at rest (future)
- No user funds touch Signal Engine infrastructure in v1
- Rate limiting on all public endpoints
- CORS restricted to frontend origin
- Audit log for all state machine transitions

---

## 18. Extension Points

When adding a new system, follow this checklist:

1. **Document it here first** — purpose, interface, inputs, outputs, status
2. Create module under the appropriate `backend/app/` directory
3. Define Pydantic schemas in `backend/app/schemas/`
4. Register with Evidence Engine (if it produces evidence)
5. Add unit tests in `backend/tests/`
6. Add API endpoint if user-facing
7. Add dashboard section if visual
8. Update this file's status column

---

## 19. Implementation Roadmap

| Milestone | Systems | Status |
|-----------|---------|--------|
| M1 — Foundation | Project structure, Docker, health API, dashboard shell | **Complete** |
| M2 — Evidence Engine | Evidence accumulation, scoring, persistence | **Complete** |
| M3 — Analysis Engines | Trend, Buyer/Seller, Derivatives, Macro, Regime | **Complete** |
| M4 — Decision Pipeline | Opportunity, Execution, Risk | **Complete** |
| M5 — AI & Dashboard | AI Analyst, live dashboard, WebSocket | **Complete** |
| M6 — Learning & Backtesting | Signal storage, backtesting, weight tuning | **Complete** |
| M7 — Market Data | Provider adapters, ingestion pipeline | Not started |
| M8 — Broker Adapters | Read-only portfolio, paper trading | Not started |

---

## 20. Related Documents

| Document | Location |
|----------|----------|
| Quick start & setup | `README.md` |
| Architecture summary | `docs/architecture/overview.md` |
| Development journal | `docs/journal/` |
| Milestone tracker | `docs/roadmap/milestones.md` |
| Research notes | `docs/research/` |

---

*This document is the source of truth for system design. If code and this document disagree, the document wins until deliberately updated.*
