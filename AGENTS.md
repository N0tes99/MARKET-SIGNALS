# AGENTS.md

## Cursor Cloud specific instructions

Signal Engine is a full‑stack app: a Python 3.12 / FastAPI backend and a Next.js 15
(React 19) frontend, backed by PostgreSQL + Redis (Celery uses Redis). Standard
commands live in `README.md`, `docker-compose.yml`, `backend/pyproject.toml`, and
`frontend/package.json`; the notes below only cover the non‑obvious, cloud‑specific
gotchas.

### Services & how they run (dev)
- Backend API — from `backend/`, `.venv/bin/uvicorn app.main:app --reload --port 8000`.
  Docs at `/docs`, health at `/api/v1/health`, dashboard data at `/api/v1/assets`
  (fetches live market data from external APIs; egress is open).
- Frontend — see the CSP caveat below; run it as a production build, not `npm run dev`.
- PostgreSQL 16 and Redis 7 are installed as system packages. They are NOT started
  automatically — start them each boot with:
  `sudo redis-server /etc/redis/redis.conf --daemonize yes` and
  `sudo pg_ctlcluster 16 main start`.
- The Postgres role/db `signal_engine`/`signal_engine` (password `signal_engine`,
  superuser) already exists. After Postgres is up, apply migrations from `backend/`
  with `.venv/bin/alembic upgrade head` before exercising DB‑backed features.

### `.env` gotchas
- Config is read from the repo‑root `.env` (see `backend/app/config/settings.py`),
  created from `.env.example`. `.env.example` points `REDIS_URL`/`CELERY_*` at the
  Docker Compose hostname `redis`; for local (non‑Docker) runs these must be
  `redis://localhost:6379/...` (already fixed in the local `.env`).
- `SIGNAL_STORE=auto` uses Postgres when reachable and silently falls back to an
  in‑memory store otherwise, so the backend boots even if Postgres/Redis are down —
  but auth, the Postgres signal store, and Celery need the real services.
- Auth/site gate are OFF locally (`AUTH_PASSWORD` and `SITE_TOTP_SECRET` empty), so the
  dashboard is reachable without logging in.

### Frontend CSP caveat (important — `npm run dev` looks broken)
`frontend/next.config.ts` sets a production CSP with `script-src 'self' 'unsafe-inline'`
(no `'unsafe-eval'`). In dev mode Next.js React Refresh evaluates code via `eval`, which
the CSP blocks, so `npm run dev` renders a page permanently stuck on "Loading…" (the
client JS never executes). To view/develop the UI in this environment, run a production
build with proxy mode instead:
- Build once: `NEXT_PUBLIC_USE_API_PROXY=true npm run build` (the `.env.production.local`
  in `frontend/` already sets this flag).
- Serve: `npx next start -p 3000`.
The browser then calls the same‑origin proxy `/api/backend/*`, which forwards to
`API_BACKEND_URL` (defaults to `http://localhost:8000`). Direct mode
(`NEXT_PUBLIC_USE_API_PROXY=false`) also fails in a production build because the CSP
`connect-src` is `'self'` only. Note: `next dev` shares the `.next/` directory, so if the
dev server ran, delete `.next/` and rebuild before `next start`.

### Lint / test / build
- Backend lint: `.venv/bin/ruff check .` (from `backend/`).
- Backend tests: run with `SIGNAL_STORE=memory` — `SIGNAL_STORE=memory .venv/bin/pytest`.
  Tests inject mock services/fixtures and do not require migrated Postgres tables (this
  matches CI in `.github/workflows/ci.yml`).
- Frontend: `npm run lint`, `npm run type-check`, `npm run build` (from `frontend/`).
