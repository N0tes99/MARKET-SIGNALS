# Signal Engine

**Signal Engine** is an AI-powered Market Intelligence Platform that helps traders make statistically superior decisions through evidence accumulation—not prediction.

> Signal Engine is **not** a trading bot. It is a decision-support platform: Bloomberg Terminal meets AI Analyst.

## Philosophy

- Protect capital first
- No trade is a valid decision
- Evidence beats prediction
- Every recommendation must be explainable
- Every feature must be measurable
- Everything should be backtestable
- AI explains decisions; it does not blindly generate them

## Architecture

All engines feed into a central **Evidence Engine**, which accumulates evidence (never predicts). The pipeline flows:

```
Evidence Engine → Opportunity Engine → Execution Engine → Risk Engine → AI Analyst
```

### Engines

| Engine | Purpose |
|--------|---------|
| Trend Engine | Market direction (Bullish / Neutral / Bearish) |
| Opportunity Engine | Asset ranking, opportunity score, trade grade |
| Execution Engine | Entry timing (WAIT / WATCH / EXECUTE) |
| Risk Engine | Position sizing, stops, drawdown limits |
| Buyer/Seller Engine | Order flow strength and absorption |
| Macro Engine | Fed, inflation, DXY, economic calendar |
| Derivatives Engine | Funding, OI, liquidations, L/S ratio |
| Regime Engine | Market regime classification |
| Learning Engine | Signal/trade/outcome storage for future weight tuning |
| AI Analyst | Human-readable reasoning from numerical evidence |

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery |
| AI | OpenAI API, local reasoning architecture |
| Frontend | Next.js, React, TypeScript, TailwindCSS, shadcn/ui, Recharts, TanStack Query |
| Infrastructure | Docker, Docker Compose, GitHub Actions, Alembic, Ruff, Pytest |

## Project Structure

```
signal-engine/
├── ARCHITECTURE.md   # System design — source of truth (read before building)
├── backend/          # FastAPI application
├── frontend/         # Next.js dashboard
├── docs/             # Architecture, roadmap, research
├── scripts/          # Utility scripts
└── docker-compose.yml
```

> **Before implementing any engine or adapter, read `ARCHITECTURE.md`.** Every major system is documented there before it is built.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### With Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Health | http://localhost:8000/api/v1/health |
| Celery worker / beat | background (Redis broker; warm cache every 5m) |

### Local Development

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

**Tests:**

```bash
cd backend
pytest
ruff check .
```

## Production deploy

See [docs/deploy.md](docs/deploy.md) for **Render (API + Postgres) + Netlify (frontend)** with HTTP Basic Auth via a Next.js proxy. Railway/Vercel are legacy — ignore for new deploys.

Local Compose also runs `celery-worker` + `celery-beat` (Redis) so `warm_market_and_decisions` fires every 5 minutes.

## Milestone Status

- [x] Project foundation (structure, Docker, health endpoint, linting, testing)
- [x] Evidence Engine (accumulation, scoring, persistence, API)
- [x] Analysis engines (Trend, Buyer/Seller, Derivatives, Macro, Regime, Risk)
- [x] Decision pipeline (Opportunity, Execution, Risk veto, MANAGE/EXIT)
- [x] Dashboard with live data (TanStack Query polling on `/api/v1/assets`)
- [x] AI Analyst integration
- [x] Backtesting framework

## License

Proprietary — All rights reserved.
