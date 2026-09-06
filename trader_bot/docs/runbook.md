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
| `--hold-seconds 5` | Paper hold before mid exit |
| `--record-books` | Also append L2 snapshots to `data/books.jsonl` |
| `--data-dir PATH` | Journal + heartbeat directory |

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
