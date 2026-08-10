# Deploy Signal Engine — Render (API + Postgres) + Netlify (frontend)

This locks the API with HTTP Basic Auth and keeps credentials off the browser
via a Next.js proxy.

## Architecture

```
Browser → Netlify (Next.js) → /api/backend/* proxy (+ Basic Auth)
                              ↓
                         Render FastAPI
                              ↓
                       Render Postgres
```

- `GET /api/v1/health` is public (Render healthchecks).
- All other API routes require Basic Auth when `AUTH_PASSWORD` is set (proxy injects it).
- Social accounts use a second layer: email/password JWT in httpOnly cookie `se_session`
  (Secure + SameSite=Lax). The `/api/backend/*` proxy forwards `Cookie` / `Set-Cookie`.
- `/docs` is disabled when `APP_ENV=production`.

> **Legacy:** Older Railway / Vercel notes are obsolete — do not use them as the
> primary path. Keep any leftover `railway.toml` / Vercel project configs only if
> you still have a legacy deployment; new deploys should be Render + Netlify.

---

## 1. Render — Postgres

1. Create a Render account and a new **PostgreSQL** instance.
2. Note the internal / external `DATABASE_URL` (often `postgres://…`).
   The app normalizes it to `postgresql+asyncpg://…` automatically.

## 2. Render — API (Web Service)

1. **New → Web Service** from the GitHub repo.
2. **Root Directory:** `backend`
3. Build/start use [`backend/Dockerfile`](../backend/Dockerfile) (or Render’s Docker runtime).
4. Start command should run `alembic upgrade head` then uvicorn on `$PORT`
   (match the Dockerfile `CMD` / entrypoint).
5. Attach the Postgres instance / copy `DATABASE_URL` into the API service env.

### Required API env vars

| Variable | Example / notes |
|----------|-----------------|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `SECRET_KEY` | long random string (**required strong in prod** — signs social JWT cookies) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | optional; default `20160` (14 days) for `se_session` cookie |
| `PUBLIC_APP_URL` | frontend origin for email verify links, e.g. `https://signals27.netlify.app` (falls back to first `CORS_ORIGINS`) |
| `DATABASE_URL` | from Render Postgres |
| `SIGNAL_STORE` | `postgres` (or `auto`) — learning outcomes, paper PnL, and Discord alert cooldowns |
| `AUTH_USERNAME` | e.g. `signal` |
| `AUTH_PASSWORD` | strong password (site lockdown Basic Auth; separate from user accounts) |
| `ADMIN_USERNAMES` | comma-separated social usernames for Outcome log (default `Admin`) |
| `CORS_ORIGINS` | your Netlify URL, e.g. `https://signals27.netlify.app` |
| `FRED_API_KEY` | optional but recommended |
| `COINGLASS_API_KEY` | optional paid — leave blank; funding/OI still run without it |

### Optional alert / email-verify vars

Same SMTP as alerts (`ALERT_SMTP_*`, `ALERT_EMAIL_FROM`). Registration sends a confirmation link when SMTP is configured (always required in `APP_ENV=production`). Social writes (post/like/follow/favorites) need a verified email.

### Social features

- `/social` — feed + compose (tracked ticker required)
- `/favorites` — per-user watchlist from tracked symbols
- Alembic migrations `004`–`006` run on API boot (`alembic upgrade head`)

### Optional Celery / Redis (local Compose primary)

Local Docker Compose runs `celery-worker` + `celery-beat` against Redis for the
warm-cache schedule (`warm_market_and_decisions` every 5 minutes). On Render’s
free web tier you typically rely on GitHub keep-warm (below) instead of a
persistent Beat process. If you add a Render Redis + background workers later,
reuse the same `CELERY_BROKER_URL` / beat schedule from `app.core.celery_app`.

### Verify API

```bash
curl https://YOUR-RENDER-URL/api/v1/health
# → 200 healthy; check stores.learning / stores.paper / stores.alerts == "postgres"

curl -u signal:YOUR_PASSWORD https://YOUR-RENDER-URL/api/v1/alerts/status
# → 200; state_backend should be "postgres"
```

---

## 3. Netlify — frontend

Repo root includes [`netlify.toml`](../netlify.toml) with `base = "frontend"` and the Next.js plugin.

1. Import the GitHub repo in Netlify (e.g. `N0tes99/MARKET-SIGNALS`).
2. In Build settings clear Publish / Functions if they show nested `frontend/` paths — rely on `netlify.toml`.
3. Environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_USE_API_PROXY` | `true` |
| `API_BACKEND_URL` | `https://YOUR-RENDER-API-URL` (no trailing slash) |
| `API_USERNAME` | same as `AUTH_USERNAME` |
| `API_PASSWORD` | same as `AUTH_PASSWORD` |

Do **not** set `NEXT_PUBLIC_API_PASSWORD`. Server-only `API_*` stays off the client bundle.

4. Deploy. Open the Netlify URL — the UI calls `/api/backend/api/v1/...`, which proxies to the API with Basic Auth.

5. After you have the frontend URL, add it to the API `CORS_ORIGINS` (comma-separated if multiple) and redeploy the API if needed.

---

## 4. Local with auth (optional)

Root `.env`:

```env
AUTH_USERNAME=signal
AUTH_PASSWORD=dev-secret
CORS_ORIGINS=http://localhost:3000
```

`frontend/.env.local`:

```env
NEXT_PUBLIC_USE_API_PROXY=true
API_BACKEND_URL=http://localhost:8000
API_USERNAME=signal
API_PASSWORD=dev-secret
```

Or keep auth off locally (empty `AUTH_PASSWORD`) and use direct `NEXT_PUBLIC_API_URL=http://localhost:8000`.

### Celery warm schedule (Compose)

`docker compose up` starts **`celery-worker`** and **`celery-beat`** on the same
Redis broker as the API. Beat publishes `app.tasks.warm_cache.warm_market_and_decisions`
every **300s** (see `beat_schedule` in `backend/app/core/celery_app.py`), which
prefetches OHLCV and warms the decision evaluate cache for tracked symbols.

---

## Keep API warm (GitHub Actions)

[`.github/workflows/keep-api-warm.yml`](../.github/workflows/keep-api-warm.yml) runs two scheduled pings (must be on the **default branch** for Actions schedules to fire):

| Ping | Cadence | Purpose |
|------|---------|---------|
| `GET /api/v1/health` | ~every 12 min | Keep the API awake / reduce free-tier cold starts |
| `GET /api/v1/assets` | ~every 30 min | Run scoring so Discord alerts can fire without site visitors |

Defaults use the Netlify proxy when variables are unset. Prefer **direct Render URLs with full paths**:

| Repo variable | Exact value |
|---------------|-------------|
| `API_HEALTH_URL` | `https://market-signals-51f0.onrender.com/api/v1/health` |
| `API_ASSETS_URL` | `https://market-signals-51f0.onrender.com/api/v1/assets` |

`/assets` is Basic-Auth protected on Render. Add Actions **secrets** (not variables):

| Secret | Value |
|--------|--------|
| `API_USERNAME` | same as Render `AUTH_USERNAME` |
| `API_PASSWORD` | same as Render `AUTH_PASSWORD` |

Do **not** set the variables to the bare hostname (`https://….onrender.com`) — that hits `/` and returns **401**. The workflow will auto-append `/api/v1/health` or `/api/v1/assets` when the variable is host-only, but prefer setting the full paths above so logs match intent.

If health still returns **401** after a full `/api/v1/health` URL, AUTH middleware is protecting health — exclude that path on Render (health must stay public).

The assets job wakes health first, waits a few seconds, then hits `/assets` (120s timeout). A cold-start 502 or timeout is expected sometimes — the step exits 0 and uses `continue-on-error`, so the run stays green/yellow, not red. Health still fails the job on real errors. Schedules can drift on free Actions minutes; cost is $0 within the free allowance.

---

## Checklist

- [ ] Render Postgres linked
- [ ] Migrations succeed on API boot (`alembic upgrade head`)
- [ ] Health public, other routes 401 without auth
- [ ] Netlify proxy env set; dashboard loads assets
- [ ] Discord/email alerts only if you want them (`ALERT_ENABLED=true`)
- [ ] Keep-warm repo vars use **full** `/api/v1/health` and `/api/v1/assets` paths
