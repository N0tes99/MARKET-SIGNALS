from __future__ import annotations

import json
from pathlib import Path

from hl_scalper.webapp import latest_ensemble, read_jsonl_tail, ui_dir


def test_ui_files_exist() -> None:
    root = ui_dir()
    assert (root / "index.html").is_file()
    assert (root / "style.css").is_file()
    assert (root / "app.js").is_file()


def test_read_jsonl_and_ensemble(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    rows = [
        {"event": "boot", "mode": "paper"},
        {
            "event": "ensemble",
            "coin": "BTC",
            "action": "enter",
            "side": "buy",
            "reason": "agree_2",
            "proposals": [{"agent": "imbalance", "kind": "enter", "side": "buy"}],
        },
        {"event": "fill", "coin": "BTC"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    events, nxt = read_jsonl_tail(path, after=0, limit=10)
    assert len(events) == 3
    assert nxt == 3
    ens = latest_ensemble(path)
    assert ens is not None
    assert ens["action"] == "enter"
