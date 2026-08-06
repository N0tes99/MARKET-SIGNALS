# Signal Engine Roadmap

## Milestone 1 — Foundation

- [x] Project structure and placeholder modules
- [x] FastAPI starter with health endpoint
- [x] Next.js dashboard starter
- [x] Docker Compose environment
- [x] SQLAlchemy + Alembic setup
- [x] CI/CD with GitHub Actions
- [x] Linting (Ruff) and testing (Pytest)

## Milestone 2 — Evidence Engine

- [x] Evidence accumulation from all engines
- [x] Weighted confidence scoring
- [x] Evidence bundle persistence
- [x] Evidence API endpoints
- [x] Dashboard evidence detail view

## Milestone 3 — Analysis Engines

- [x] Market data layer (Binance provider + mock provider)
- [x] Technical indicators (EMA, RSI, MACD, ATR, volume)
- [x] Trend Engine with EMA/RSI/MACD
- [x] Buyer/Seller Engine
- [x] Derivatives Engine
- [x] Macro Engine (FRED optional)
- [x] Regime Engine with weight multipliers
- [x] Risk Engine evidence contribution

## Milestone 4 — Decision Pipeline

- [x] Opportunity Engine ranking
- [x] Execution Engine timing
- [x] Risk Engine position sizing (pipeline integration)
- [x] Kraken fallback for US geo-restrictions

## Milestone 5 — AI & Dashboard

- [x] AI Analyst with OpenAI integration (+ local fallback)
- [x] Live dashboard auto-refresh (30s polling)
- [x] WebSocket dashboard endpoint
- [x] Asset detail views with decision banner + AI explanation

## Milestone 6 — Learning & Backtesting

- [x] Learning Engine signal storage (in-memory ring buffer)
- [x] Historical similarity search (cosine on evidence vectors)
- [x] Walk-forward backtesting framework
- [x] Scoring weight optimization
- [x] Outcome logging (hit/miss + realized return)
- [x] Postgres signal_records persistence (auto-fallback to memory)

## Milestone 7 — Market Data & Ops

- [x] Celery market data ingestion / warm cache (`app.tasks.warm_cache.warm_market_and_decisions`)
- [ ] Stale data detection
- [x] Production deploy scaffolding (Basic Auth + Railway/Vercel docs) — wire accounts in [docs/deploy.md](../deploy.md)
- [x] Alerting on high-confidence setups (Discord bot / webhook + email)
