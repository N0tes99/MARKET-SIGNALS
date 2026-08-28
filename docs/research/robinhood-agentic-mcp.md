# Robinhood Agentic — dual MCP (parked)

> **Status:** Open idea. **Do not build yet.**
> **Last updated:** 2026-08-28

Signal Engine stays an intelligence desk. Robinhood Agentic Trading (May 2026) is a
user-owned MCP at `https://agent.robinhood.com/mcp/trading` (OAuth 2.1 + PKCE on
desktop). This is **not** a new Rail, not a Render-hosted bot, and not unofficial
`robin_stocks` scraping.

---

## Product split

| Piece | Who hosts it | Job |
|-------|----------------|-----|
| Signal Engine MCP (not built) | Us | Read-only: hot picks, decision, evidence, paper ledger, rail desk |
| Robinhood Trading MCP | Robinhood | Read all RH accounts; `place_*` / `cancel_*` only in a separately funded **Agentic** account |
| Agent client | User (Cursor / Claude / Codex) | Orchestrates both. Never our keep-warm or Celery. |

The model asks **us** whether a name is a trade, then may call Robinhood
`review_equity_order` and only then `place_equity_order` if the user asked it to.

We do **not** call `place_*` from FastAPI, Render, or GitHub keep-warm.

---

## Why it is parked

- No Alpaca-style REST key. Auth is per-user OAuth; schema is `tools/list` at runtime.
- Alpaca stays the env-key **read-only** equity mirror we already have.
- Crypto live execution, if any, stays **Rail** (`docs/research/rail-execution-surface.md`) in a separate process. Robinhood crypto `place_crypto_order` is still their agent, not ours.
- Robinhood’s own disclosure: the user owns every agent fill; they do not supervise the third-party agent.

---

## If we pick it up later (not a schedule)

1. Read-only Signal Engine MCP wrapping existing APIs (`/assets`, `/decision`, `/paper/summary`, `/rail/desk`). No `place_order` tools.
2. Optional RH **read** mirror (positions / fills), same pattern as `GET /api/v1/brokers/alpaca/mirror`.
3. Optional `review_*` clerk. Still no `place_*` on our host.

Do not start those slices until this status changes.
