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
- **Site Authenticator gate:** when `SITE_TOTP_SECRET` is set, browsers must unlock
  via `/unlock` with a 6-digit TOTP code; unlock sets httpOnly cookie `se_mfa`
  (default 12h). API also requires that cookie (Basic Auth alone is not enough).
- Social accounts use a second layer: email/password JWT in httpOnly cookie `se_session`
  (Secure + SameSite=Lax). The `/api/backend/*` proxy forwards `Cookie` / `Set-Cookie`.
- `/docs` is disabled when `APP_ENV=production`.

> **Legacy:** Older Railway / Vercel notes are obsolete — do not use them.
> New deploys should be Render + Netlify.

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

Render **free** web services are **512MB**. Dashboard load used to OOM-restart
the dyno (paper tick + `rank_all` + Radar/Expansion/tape all at once, plus a
50k-bar in-RAM warehouse copy of Postgres). The API now caps thread pools,
does not duplicate warehouse bars in process memory when Postgres is up, and
sets `MALLOC_ARENA_MAX=2`. `/api/v1/health` includes `rss_mb` so you can see
the spike. If it still hits 512MB, the next step is a paid instance, not more
scanners on boot.

### Required API env vars

| Variable | Example / notes |
|----------|-----------------|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` (forced off when `APP_ENV=production`, even if unset or `true`) |
| `SECRET_KEY` | long random string (**required** — app refuses to start in production with the default `change-me-in-production`; signs social JWT cookies) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | optional; default `20160` (14 days) for `se_session` cookie |
| `PUBLIC_APP_URL` | frontend origin for email verify links, e.g. `https://your-site.netlify.app` (falls back to first `CORS_ORIGINS`) |
| `DATABASE_URL` | from Render Postgres |
| `SIGNAL_STORE` | `postgres` (or `auto`) — learning outcomes, paper PnL, and Discord alert cooldowns |
| `AUTH_USERNAME` | e.g. `signal` |
| `AUTH_PASSWORD` | **required in production** — app refuses to start without it. Strong password (site lockdown Basic Auth; separate from user accounts) |
| `CRON_SECRET` | shared secret for `POST /api/v1/paper/cron-tick` (GitHub Actions keep-warm). Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `REDDIT_SOCIAL_ENABLED` | optional; default `true` — per-ticker Reddit confirmation in Sentiment (~35% of the small Sentiment weight). Set `false` to skip Reddit entirely (Fear & Greed still runs) |
| `REDDIT_CLIENT_ID` | **required for live Reddit on Render** — from [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (script or web app). Public JSON is blocked on datacenter IPs |
| `REDDIT_CLIENT_SECRET` | pair with `REDDIT_CLIENT_ID` (leave blank only for “installed app” type). Never commit this |
| `REDDIT_USER_AGENT` | optional; Reddit-preferred format `platform:app:version (contact)`. Default is already set |
| `SITE_TOTP_SECRET` | **required in production** — app refuses to start empty. Base32 **gate switch only** (not a login HMAC key). Per-user authenticator secrets are encrypted at rest with `SECRET_KEY`. Rotating `SECRET_KEY` invalidates sessions **and** stored TOTP blobs — users must re-enroll. |
| `SITE_TOTP_ISSUER` | optional; default `Signal Engine` |
| `SITE_GATE_EXPIRE_HOURS` | optional; default `12` (MFA cookie lifetime, capped by grant expiry) |
| `ADMIN_USERNAMES` | comma-separated social usernames for Outcome log + `/admin/access`. Default `Admin` is reserved — registration of those names is refused. Use a hard-to-guess handle you already own. |
| `CORS_ORIGINS` | your Netlify URL, e.g. `https://your-site.netlify.app` |
| `FRED_API_KEY` | optional but recommended |
| `COINGLASS_API_KEY` | optional paid — leave blank; funding/OI still run via Bybit→OKX without it |
| `ALPACA_API_KEY` | optional — Alpaca read-only mirror of positions/fills (no order execution) + free IEX activity |
| `ALPACA_API_SECRET` | optional — pair with `ALPACA_API_KEY`; leave both blank to show empty state |
| `ALPACA_BASE_URL` | optional; default `https://paper-api.alpaca.markets` (paper). Use `https://api.alpaca.markets` for live keys |
| `ALPACA_DATA_BASE_URL` | optional; default `https://data.alpaca.markets` — Market Data host for **IEX-only** free snapshots (`feed=iex`). Never request SIP / Algo Trader Plus. Yahoo remains primary OHLCV. |
| `GROQ_API_KEY` | optional **free** GroqCloud vision for Chart. https://console.groq.com/keys |
| `RAIL_ARMED` | optional; default `false`. Master kill switch for Surface 6 clerk submits. Leave off. |
| `RAIL_LIVE_ENABLED` | optional; default `false`. Live adapters **refuse even when true**. Do not put venue signing keys on Render. |
| `HYPERLIQUID_INFO_URL` | optional; default `https://api.hyperliquid.xyz` — public `/info` only (Phase B scanners). Never point this at `/exchange`. |
| `DATA_LAKE_PATH` | optional local parquet dump of `ohlcv_bars`. **Leave empty on Render** (ephemeral disk). Empty warehouse → no files. |

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
# After 020: alembic.at_head true, alembic.current "020" (or later),
# warehouse.table_present true. warehouse.bar_count grows after keep-warm /assets
# and cortex ticks write 5m/15m/1h/4h/1d bars. Zero bars = lake not ready (no parquet yet).

curl -u signal:YOUR_PASSWORD https://YOUR-RENDER-URL/api/v1/alerts/status
# → 200; state_backend should be "postgres"

curl -u signal:YOUR_PASSWORD https://YOUR-RENDER-URL/api/v1/data-lake/status
# → warehouse + alembic snapshot (same fields as health, behind Basic Auth)
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
| `NEXT_PUBLIC_REQUIRE_LOGIN` | `true` (login → grant → authenticator before dashboard) |
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

[`.github/workflows/keep-api-warm.yml`](../.github/workflows/keep-api-warm.yml) runs scheduled pings (must be on the **default branch** for Actions schedules to fire):

| Ping | Cadence | Purpose |
|------|---------|---------|
| `GET /api/v1/health` | ~every 10 min | Cheap liveness ping — must **not** construct PaperAgent |
| `POST /api/v1/paper/cron-tick` | right after health (retries 502) | Advance paper bot before the heavy rank |
| `GET /api/v1/assets?sync=true` | after paper tick | Full `rank_all` so memory + Postgres dashboard cache stay warm |

Browser dashboard calls `GET /api/v1/assets` **without** `sync` and receives a snapshot immediately (`ranking_status`: `fresh` / `stale` / `warming`). Cold misses refresh in the background so Netlify’s proxy does not wait on a full rank.

Store Render URLs as Actions **secrets** (not variables). Secrets are redacted as `***` in public logs; variables are not. The workflow still reads Variables as a fallback until you move them.

| Actions secret | Exact value |
|----------------|-------------|
| `API_HEALTH_URL` | `https://<your-render-service>.onrender.com/api/v1/health` |
| `API_ASSETS_URL` | `https://<your-render-service>.onrender.com/api/v1/assets` |
| `API_FUTURES_BOARD_URL` | optional; defaults from health host → `/api/v1/futures/board` |
| `API_PAPER_CRON_URL` | optional; defaults from health host → `/api/v1/paper/cron-tick` |

`/assets` and `/paper/cron-tick` bypass the MFA product gate (so keep-warm works without a browser session) but stay **Basic-Auth** protected on Render. Also add:

| Secret | Value |
|--------|--------|
| `API_USERNAME` | same as Render `AUTH_USERNAME` |
| `API_PASSWORD` | same as Render `AUTH_PASSWORD` |
| `CRON_SECRET` | same as Render `CRON_SECRET` |

After the URL secrets work, delete the matching **Variables** so the hostname is not listed in Settings either.

Do **not** set a URL to the bare hostname (`https://….onrender.com`) — that hits `/` and returns **401**. The workflow will auto-append `/api/v1/health` or `/api/v1/assets` when the value is host-only. Derived futures/paper URLs stay in the job script and are not written to `GITHUB_ENV`, so logs show HTTP codes only (`Pinging futures`, `OK (HTTP 200)`), not hosts.

If health still returns **401** after a full `/api/v1/health` URL, AUTH middleware is protecting health — exclude that path on Render (health must stay public).

The assets job wakes health first, waits a few seconds, ticks the paper bot (with 502 retries), then hits `/assets?sync=true` (180s timeout). Ranking snapshots also persist in `paper_agent_state` (`dashboard_assets_v1`) so `hot_picks` survive Render disk wipes. A cold-start 502 or timeout is expected sometimes — the step exits 0 and uses `continue-on-error`, so the run stays green/yellow, not red. Health still fails the job on real errors. Schedules can drift on free Actions minutes; cost is $0 within the free allowance.

---

## Checklist

- [ ] Render Postgres linked
- [ ] Migrations succeed on API boot (`alembic upgrade head`)
- [ ] Health public, other routes 401 without auth
- [ ] Netlify proxy env set; dashboard loads assets
- [ ] Discord/email alerts only if you want them (`ALERT_ENABLED=true`)
- [ ] Keep-warm **secrets** use **full** `/api/v1/health` and `/api/v1/assets` paths (then delete the old Variables)
