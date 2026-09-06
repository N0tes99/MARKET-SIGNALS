# Automation rails — executable HL scalper

Status: **design / Phase 0 complete**  
Audience: make `trader_bot` a supervised process that can paper-run unattended, then
(later) micro-live with dual-control arming.

---

## The wallet thing (read this first)

Hyperliquid does **not** use a single “bot wallet” the way a CEX API key does.

| Role | What it does | What it must never do |
|------|----------------|------------------------|
| **Master wallet** | Holds USDC / margin; **only** key that can withdraw | Sit on a VPS, CI, Render, or in this repo |
| **Agent (API) wallet** | Authorized by master to **sign orders** on HL `/exchange` | Hold withdraw power; ever land on Signal Engine / Render |

That split is the “something else” beyond “we use crypto wallets.” Rail Phase C
already assumes it ([`docs/research/rail-execution-surface.md`](../docs/research/rail-execution-surface.md)):
separate process, agent wallet, dual-control arming, keys never on the API host.

We also need **dual-control arming** (not just a key):

1. Config / env: `LIVE_ENABLED=true`
2. Local arm file the operator creates by hand (e.g. `data/ARMED`)
3. Kill switch clear (not tripped)
4. Agent wallet present + approved on HL for this master

Any one missing → sit out / refuse live. Paper mode needs none of these.

---

## Full automation map

```
                    ┌─────────────────────────────────────┐
                    │  Supervisor (systemd / docker)      │
                    │  restart, health, log rotate        │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ BookFeed │──►│ Strategy │──►│ RiskGate │──►│ Executor │
│ /info+WS │   │ imbalance│   │ + kill   │   │ paper/   │
└──────────┘   └──────────┘   └────┬─────┘   │ live stub│
                                   │         └────┬─────┘
                                   ▼              ▼
                            ┌──────────┐   ┌──────────┐
                            │ Arming   │   │ Journal  │
                            │ + wallet │   │ JSONL +  │
                            │ approve  │   │ metrics  │
                            └──────────┘   └────┬─────┘
                                                ▼
                                         ┌──────────┐
                                         │ Reconcile│
                                         │ HL user  │
                                         │ state    │
                                         └──────────┘
```

### Rail checklist (what “executable” means)

| # | Rail | Job | Phase |
|---|------|-----|-------|
| 1 | **Feed** | Poll `/info` then WS `l2Book`; stale-book detection | 1–2 |
| 2 | **Strategy** | Pure imbalance → `Signal` or sit-out | 0 (done) |
| 3 | **Sizer** | Notional from equity, leverage cap, fee-aware min edge | 1 |
| 4 | **RiskGate** | Max positions, daily loss, consecutive losses, error budget | 0 stub → 3 |
| 5 | **Kill switch** | Trip → flat intent + refuse new entries until manual clear | 3 |
| 6 | **Arming** | Dual-control for live; paper always allowed | 3–4 |
| 7 | **Wallet vault** | Load agent key from OS secret / file mode 600; never git | 4 |
| 8 | **Executor** | Paper sim now; HL signed `/exchange` later | 0 / 4 |
| 9 | **Position mgr** | Entry → hold budget → exit (flip / time / stop) | 2 |
| 10 | **Journal** | Append-only JSONL: signal, fill, exit, kill, errors | 1 |
| 11 | **Metrics** | Expectancy, win rate, sit-out %, fee drag, latency | 2 |
| 12 | **Reconcile** | Compare local open vs HL `clearinghouseState` | 4 |
| 13 | **Supervisor** | Process manager, boot, crash restart, disk for journal | 1 |
| 14 | **Alerts** | Optional Discord/Telegram on kill / daily summary | 3 |
| 15 | **Clock / safety** | NTP skew, rate-limit backoff, idempotent client order ids | 3–4 |

Signal Engine Celery / keep-warm / Netlify are **not** rails for this bot. This
process runs on a box you control (local VM, private VPS). SE stays the desk.

---

## Executable modes

| Mode | Command shape | Needs |
|------|---------------|--------|
| **paper-once** | `python -m hl_scalper.loop --mode paper --once` | Network to `/info` |
| **paper-daemon** | same without `--once` under systemd | Journal dir writable |
| **replay** | `python -m hl_scalper.replay data/books/*.jsonl` | Recorded books only |
| **live** | `--mode live` | All four arming gates + agent wallet |

Default forever: paper. Live is opt-in and loud.

---

## Phased build order (automation-first)

### Phase 1 — Unattended paper daemon
- [x] Robust poll loop + JSONL journal + crash-safe append
- [x] `Sizer` + timed mark-to-mid exit (`hold_seconds`)
- [x] `systemd` unit example (`deploy/hl-scalper.service`)
- [x] Health file: `data/heartbeat.json` updated each tick
- [ ] Overnight paper run validation (operator)

### Phase 2 — Scalp automation (still paper)
- WS book stream
- Position manager: hold 2–30s, exit on imbalance flip / adverse mid / time
- Fee + funding drag in journal
- Nightly `report` CLI: expectancy / sit-out / kill events

### Phase 3 — Make failure safe
- Kill switch + arm file clear
- Error budget (N consecutive feed failures → kill)
- Replay harness for deterministic regression
- Alert hook on kill

### Phase 4 — Micro-live on agent wallet
- HL approve agent from master (manual, one-time in wallet UI)
- Signing module talks `/exchange` only from this process
- Reconcile loop before each entry
- Dust size + promote only after paper metrics stay green

---

## What we will not wire

- Master wallet private key anywhere automated
- Signing keys on Render / Netlify / GitHub Actions keep-warm
- Bot driven by SE `/assets` grades or LLM “should I buy”
- Cross-venue: signal on Binance, fill on HL

---

## Immediate next implementation slice

1. Harden paper loop + journal schema + heartbeat
2. Add `docs/runbook.md` (start/stop, kill clear, arm live)
3. Add example `deploy/hl-scalper.service` (systemd)
4. Record book snapshots for replay before any live talk
