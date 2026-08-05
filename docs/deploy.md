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
- All other API routes require Basic Auth when `AUTH_PASSWORD` is set.
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
| `SECRET_KEY` | long random string |
| `DATABASE_URL` | from Railway Postgres |
| `SIGNAL_STORE` | `postgres` (or `auto`) |
| `AUTH_USERNAME` | e.g. `signal` |
| `AUTH_PASSWORD` | strong password |
| `CORS_ORIGINS` | your Vercel URL, e.g. `https://your-app.vercel.app` |
| `FRED_API_KEY` | optional but recommended |

### Optional alert vars

Same as local: `ALERT_*`, Discord bot token/channel, SMTP, etc.

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
| `API_BACKEND_URL` | `https://YOUR-RAILWAY-URL` (no trailing slash) |
| `API_USERNAME` | same as `AUTH_USERNAME` |
| `API_PASSWORD` | same as `AUTH_PASSWORD` |

Do **not** set `NEXT_PUBLIC_API_PASSWORD`. Server-only `API_*` stays off the client bundle.

5. Deploy. Open the Vercel URL — the UI calls `/api/backend/api/v1/...`, which proxies to Railway with Basic Auth.

6. After you have the Vercel URL, add it to Railway `CORS_ORIGINS` (comma-separated if multiple) and redeploy the API if needed.

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

## Checklist

- [ ] Railway Postgres linked
- [ ] Migrations succeed on API boot (`alembic upgrade head`)
- [ ] Health public, other routes 401 without auth
- [ ] Vercel proxy env set; dashboard loads assets
- [ ] Discord/email alerts only if you want them (`ALERT_ENABLED=true`)
