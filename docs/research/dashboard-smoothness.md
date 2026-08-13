# Dashboard smoothness notes

## What felt slow

1. Secondary feeds (paper tick, equity options Yahoo chains, options tape, alpaca) mounted **above / alongside** rankings and competed on cold start.
2. Paper agent polled with `tick=true` every 2 minutes — a write-ish side effect on a read path.
3. Soft navigations re-checked gate status and blanked the whole app with “Loading…”.
4. Dense asset grids used `backdrop-filter: blur(18px)` on dozens of cards — expensive paint.
5. Asset cards were not memoized, so quote refreshes re-rendered the full grid.
6. Setup / equity feeds used blocking TTL `get_or_set` — cold/expired refreshes stalled the request.

## Changes in this PR

| Area | Change |
|------|--------|
| Dashboard order | Top picks + asset grid first; defer secondary strips after idle |
| Paper agent | Poll with `tick=false`; one idle tick after mount |
| Gate | React Query cache; keep UI when already granted |
| Cards | `React.memo` + `surface-dense` (no blur) |
| Charts | Slower candle poll; lazy-load Recharts line mode |
| Feeds | Stale-while-revalidate for crypto/equity/runner caches |
| Nav | `app/loading.tsx` for route transitions |

## Still worth later

- BFF `GET /dashboard` aggregate
- Seed API list cache from Celery warm (worker ≠ API process memory today)
- Parallel evidence collectors / dedupe risk assess
- Virtualize 60-symbol list
- Direct SSE/WS for quotes (Next proxy cannot upgrade WS today)
