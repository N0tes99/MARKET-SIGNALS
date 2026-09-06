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
| `--no-ws` | Disable websocket books (HTTP poll only) |

## Report

```bash
python3 -m hl_scalper.report --journal data/journal.jsonl
```

## Live arming (not trading yet)

Live **refuses** unless all of these pass — and even then the `/exchange` signer
is not wired (`allow_live_orders` still blocks real orders):

1. `LIVE_ENABLED=true`
2. `ALLOW_LIVE_ORDERS=true` (explicit product gate)
3. `data/ARMED` file exists (touch by hand)
4. `HL_AGENT_PRIVATE_KEY` set (agent only)
5. `HL_MASTER_ADDRESS` set (address only — **never** `HL_MASTER_PRIVATE_KEY`)
6. Kill switch clear; reconcile flat before entries

```bash
# Will still refuse until Phase 4 signer exists:
LIVE_ENABLED=true ALLOW_LIVE_ORDERS=true \
  HL_AGENT_PRIVATE_KEY=0x... HL_MASTER_ADDRESS=0x... \
  touch data/ARMED && python3 -m hl_scalper.loop --mode live --once
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
