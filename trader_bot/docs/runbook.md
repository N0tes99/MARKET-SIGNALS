# Runbook — HL scalper lab

## Paper daemon (local)

```bash
cd trader_bot
python3 -m pip install -e ".[dev]"
python3 -m hl_scalper.loop --mode paper --once          # one tick
python3 -m hl_scalper.loop --mode paper --data-dir data # daemon (Ctrl+C)
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--coins BTC,ETH` | Universe subset |
| `--interval 1` | Poll seconds |
| `--hold-seconds 5` | Max paper hold before time exit |
| `--record-books` | Also append L2 snapshots to `data/books.jsonl` |
| `--data-dir PATH` | Journal + heartbeat + arm file directory |
| `--ensemble` | Multi-agent desk (min 2 agree; disagreement sits out) |

## Report

```bash
python3 -m hl_scalper.report --journal data/journal.jsonl
```

## Live arming

Ladder (all required for real posts):

1. `LIVE_ENABLED=true`
2. `ALLOW_LIVE_ORDERS=true`
3. `data/ARMED` exists
4. `HL_AGENT_PRIVATE_KEY` (agent only)
5. `HL_MASTER_ADDRESS` (address only — never `HL_MASTER_PRIVATE_KEY`)
6. `DRY_RUN_LIVE=false` (defaults **true** — dry-run even when armed)
7. Kill clear + reconcile flat

```bash
LIVE_ENABLED=true ALLOW_LIVE_ORDERS=true DRY_RUN_LIVE=true \
  HL_AGENT_PRIVATE_KEY=0x... HL_MASTER_ADDRESS=0x... \
  touch data/ARMED
python3 -m hl_scalper.loop --mode live --once --coins BTC
```

## Pixel agent desk UI

```bash
# terminal A — bot
python3 -m hl_scalper.loop --mode paper --ensemble --data-dir data --coins BTC,ETH

# terminal B — UI
python3 -m hl_scalper.webapp --data-dir data --port 8787
```

Open http://127.0.0.1:8787 — live agent votes, decision board, and event tape.

## Replay

```bash
python3 -m hl_scalper.loop --mode paper --record-books --data-dir data
python3 -m hl_scalper.replay --books data/books.jsonl --data-dir data
python3 -m hl_scalper.report --journal data/replay_journal.jsonl
```

## Artifacts

| File | Purpose |
|------|---------|
| `data/journal.jsonl` | boot / signal / fill / exit / kill / errors |
| `data/heartbeat.json` | last successful tick (supervisor probe) |
| `data/books.jsonl` | optional recorded books for later replay |

## systemd

```bash
sudo cp deploy/hl-scalper.service /etc/systemd/system/
# Edit WorkingDirectory / ExecStart paths first
sudo systemctl daemon-reload
sudo systemctl enable --now hl-scalper
journalctl -u hl-scalper -f
```

Heartbeat stale check (example): if `heartbeat.json` `ts` older than 30s, alert.

## Kill switch

Trips on daily loss or repeated feed failures. Cleared only by **restarting**
the process after fixing the cause (Phase 3 will add an explicit clear file).

## Live (not yet)

`--mode live` refuses unless `Settings.live_enabled` is true **and** Phase 4
agent-wallet + arm file gates exist. Do not put master wallet keys on this host.
See [`automation-rails.md`](automation-rails.md).
