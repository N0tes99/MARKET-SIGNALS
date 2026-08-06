# Deploy Signal Engine — Railway (API + Postgres) + Vercel (frontend)

This locks the API with HTTP Basic Auth and keeps credentials off the browser
via a Next.js proxy.

## Architecture

```
Browser → Vercel (Next.js) → /api/backend/* proxy (+ Basic Auth)
                              ↓
                         Railway FastAPI
                              ↓
                       Railway Postgres
```

- `GET /api/v1/health` is public (Railway healthchecks).
- All other API routes require Basic Auth when `AUTH_PASSWORD` is set (proxy injects it).
- Social accounts use a second layer: email/password JWT in httpOnly cookie `se_session`
  (Secure + SameSite=Lax). The `/api/backend/*` proxy forwards `Cookie` / `Set-Cookie`.
- `/docs` is disabled when `APP_ENV=production`.

---

## 1. Railway — Postgres

1. Create a Railway project.
2. **New → Database → PostgreSQL**.
3. Note the `DATABASE_URL` variable (Railway often uses `postgres://…`).
   The app normalizes it to `postgresql+asyncpg://…` automatically.

## 2. Railway — API service

1. **New → GitHub Repo** (or empty service + Dockerfile).
2. Set **Root Directory** to `backend`.
3. Builder uses [`backend/Dockerfile`](../backend/Dockerfile) + [`railway.toml`](../backend/railway.toml).
4. Start command runs `alembic upgrade head` then uvicorn on `$PORT`.
5. Attach the Postgres service / copy `DATABASE_URL` into the API service.

### Required API env vars

| Variable | Example / notes |
|----------|-----------------|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `SECRET_KEY` | long random string (**required strong in prod** — signs social JWT cookies) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | optional; default `20160` (14 days) for `se_session` cookie |
| `PUBLIC_APP_URL` | frontend origin for email verify links, e.g. `https://signals27.netlify.app` (falls back to first `CORS_ORIGINS`) |
| `DATABASE_URL` | from Render Postgres |
| `SIGNAL_STORE` | `postgres` (or `auto`) |
| `AUTH_USERNAME` | e.g. `signal` |
| `AUTH_PASSWORD` | strong password (site lockdown Basic Auth; separate from user accounts) |
| `CORS_ORIGINS` | your Netlify URL, e.g. `https://signals27.netlify.app` |
| `FRED_API_KEY` | optional but recommended |

### Optional alert / email-verify vars

Same SMTP as alerts (`ALERT_SMTP_*`, `ALERT_EMAIL_FROM`). Registration sends a confirmation link when SMTP is configured (always required in `APP_ENV=production`). Social writes (post/like/follow/favorites) need a verified email.

### Social features

- `/social` — feed + compose (tracked ticker required)
- `/favorites` — per-user watchlist from tracked symbols
- Alembic migrations `004`–`006` run on API boot (`alembic upgrade head`)


### Verify API

```bash
curl https://YOUR-RAILWAY-URL/api/v1/health
# → 200 healthy

curl -u signal:YOUR_PASSWORD https://YOUR-RAILWAY-URL/api/v1/alerts/status
# → 200
```

---

## 3. Vercel — frontend

1. Import the same GitHub repo in Vercel.
2. **Root Directory:** `frontend`
3. Framework preset: Next.js (default).
4. Environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_USE_API_PROXY` | `true` |
| `API_BACKEND_URL` | `https://YOUR-API-URL` (no trailing slash) |
| `API_USERNAME` | same as `AUTH_USERNAME` |
| `API_PASSWORD` | same as `AUTH_PASSWORD` |

Do **not** set `NEXT_PUBLIC_API_PASSWORD`. Server-only `API_*` stays off the client bundle.

5. Deploy. Open the Vercel URL — the UI calls `/api/backend/api/v1/...`, which proxies to the API with Basic Auth.

6. After you have the frontend URL, add it to the API `CORS_ORIGINS` (comma-separated if multiple) and redeploy the API if needed.

## 3b. Netlify — frontend (alternative to Vercel)

Repo root includes [`netlify.toml`](../netlify.toml) with `base = "frontend"` and the Next.js plugin.

1. Import **N0tes99/MARKET-SIGNALS** in Netlify.
2. In Build settings clear Publish / Functions if they show nested `frontend/` paths — rely on `netlify.toml`.
3. Same env vars as Vercel (`NEXT_PUBLIC_USE_API_PROXY`, `API_BACKEND_URL`, `API_USERNAME`, `API_PASSWORD`).
4. Deploy, then set API `CORS_ORIGINS` to `https://your-site.netlify.app`.

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

Do **not** set the variables to the bare hostname (`https://….onrender.com`) — that hits `/` and returns **401**.

The assets job wakes health first, waits a few seconds, then hits `/assets` (120s timeout). A cold-start 502 or timeout is expected sometimes — the step exits 0 and uses `continue-on-error`, so the run stays green/yellow, not red. Health still fails the job on real errors. Schedules can drift on free Actions minutes; cost is $0 within the free allowance.

---

## Checklist

- [ ] Railway Postgres linked
- [ ] Migrations succeed on API boot (`alembic upgrade head`)
- [ ] Health public, other routes 401 without auth
- [ ] Vercel proxy env set; dashboard loads assets
- [ ] Discord/email alerts only if you want them (`ALERT_ENABLED=true`)
