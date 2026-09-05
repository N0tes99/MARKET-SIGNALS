# AGENTS.md

## Cursor Cloud specific instructions

Signal Engine is a full-stack app: a Python 3.12 / FastAPI backend and a Next.js 15
(React 19) frontend, backed by PostgreSQL + Redis (Celery uses Redis). Standard
commands live in `README.md`, `docker-compose.yml`, `backend/pyproject.toml`, and
`frontend/package.json`; the notes below only cover the non-obvious, cloud-specific
gotchas.

### Services & how they run (dev)

- Backend API — from `backend/`, `python -m uvicorn app.main:app --reload --port 8000`.
  Docs at `/docs`, health at `/api/v1/health`, dashboard data at `/api/v1/assets`
  (fetches live market data from external APIs; egress is open).
- Frontend — see the CSP caveat below; run it as a production build, not `npm run dev`.
- PostgreSQL 16 and Redis 7 are installed as system packages. They are NOT started
  automatically — start them each boot with:
  `sudo redis-server /etc/redis/redis.conf --daemonize yes` and
  `sudo pg_ctlcluster 16 main start`.
- The Postgres role/db `signal_engine`/`signal_engine` (password `signal_engine`,
  superuser) already exists. After Postgres is up, apply migrations from `backend/`
  with `alembic upgrade head` before exercising DB-backed features.

### `.env` gotchas

- Config is read from the repo-root `.env` (see `backend/app/config/settings.py`).
  Create an empty file with `touch .env` and add local keys there. **Never commit
  `.env`.** There is no public `.env.example` in the repo; env var names live in
  [`docs/deploy.md`](docs/deploy.md).
- Defaults already point Redis/Celery at `localhost`. Docker Compose overrides these
  to the hostname `redis`. Do not copy Compose `REDIS_URL=redis://redis:6379/0` into a
  non-Docker local `.env`.
- `SIGNAL_STORE=auto` uses Postgres when reachable and silently falls back to an
  in-memory store otherwise, so the backend boots even if Postgres/Redis are down —
  but auth, the Postgres signal store, and Celery need the real services.
- Auth/site gate are OFF locally (`AUTH_PASSWORD` and `SITE_TOTP_SECRET` empty), so the
  dashboard is reachable without logging in. Production Netlify sets
  `NEXT_PUBLIC_REQUIRE_LOGIN=true`.
- Chart screenshot analysis needs `GROQ_API_KEY` on the **API** host (Render in
  production). Do not point public Render at a home LM Studio URL.

### Frontend CSP caveat (production vs `next start`)

`frontend/middleware.ts` sets a **production** CSP with a per-request script nonce and
`'strict-dynamic'` (CSP3 then ignores `'unsafe-inline'` on `script-src`). Styles still
allow `'unsafe-inline'` because Tailwind/Next inject inline CSS. The policy is **not**
applied during `next dev`, so React Refresh/`eval` works.

A production build (`next start` / Netlify) uses `connect-src 'self'` only. Use
`NEXT_PUBLIC_USE_API_PROXY=true` so the browser hits `/api/backend`. Direct mode
(`NEXT_PUBLIC_USE_API_PROXY=false`) cannot call `localhost:8000` under that CSP.
Note: `next dev` shares the `.next/` directory, so if the dev server ran, delete `.next/`
and rebuild before `next start`.

### Lint / test / build

- Backend lint: `ruff check .` (from `backend/`).
- Backend tests: run with `SIGNAL_STORE=memory` —
  `SIGNAL_STORE=memory pytest`.
  Tests inject mock services/fixtures and do not require migrated Postgres tables (this
  matches CI in `.github/workflows/ci.yml`).
- Frontend: `npm run lint`, `npm run type-check`, `npm run build` (from `frontend/`).
