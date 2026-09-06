from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hl_scalper.agents.desk import AgentDesk
from hl_scalper.agents.protocol import DeskDecision, Proposal
from hl_scalper.config import Settings
from hl_scalper.risk import RiskGate
from hl_scalper.strategy import Signal
from hl_scalper.webapp import (
    heartbeat_payload,
    journal_stats,
    latest_ensemble,
    make_handler,
    read_jsonl_tail,
    ui_dir,
    _static_file,
)


def test_ui_files_exist() -> None:
    root = ui_dir()
    assert (root / "index.html").is_file()
    assert (root / "style.css").is_file()
    assert (root / "app.js").is_file()
    html = (root / "index.html").read_text(encoding="utf-8")
    assert 'role="log"' in html
    assert "aria-live" in html
    css = (root / "style.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    js = (root / "app.js").read_text(encoding="utf-8")
    assert "inFlight" in js
    assert "textContent" in js


def test_read_jsonl_cursor_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    path.write_text(
        '{"event":"a"}\n\n{"event":"b"}\n{"event":"c"}\n',
        encoding="utf-8",
    )
    events, nxt = read_jsonl_tail(path, after=0, limit=2)
    assert [e["event"] for e in events] == ["a", "b"]
    assert nxt == 3  # line index after blank + two events
    events2, nxt2 = read_jsonl_tail(path, after=nxt, limit=10)
    assert [e["event"] for e in events2] == ["c"]
    assert nxt2 == 4


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
        {
            "event": "ensemble",
            "coin": "ETH",
            "action": "sit_out",
            "reason": "disagreement",
            "proposals": [],
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    events, nxt = read_jsonl_tail(path, after=0, limit=10)
    assert len(events) == 4
    assert nxt == 4
    ens = latest_ensemble(path)
    assert ens is not None
    assert ens["coin"] == "ETH"
    assert ens["action"] == "sit_out"


def test_journal_stats(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    rows = [
        {"event": "fill"},
        {"event": "fill"},
        {"event": "exit", "pnl_usd": 1.5},
        {"event": "exit", "pnl_usd": -0.25},
        {"event": "sit_out"},
        {"event": "ensemble", "action": "sit_out"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    stats = journal_stats(path)
    assert stats["fills"] == 2
    assert stats["exits"] == 2
    assert stats["sit_outs"] == 1
    assert abs(float(stats["pnl_usd"]) - 1.25) < 1e-9
    assert stats["lines"] == 6


def test_heartbeat_stale(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat.json"
    fresh = {
        "ts": datetime.now(UTC).isoformat(),
        "mode": "paper",
        "ticks": 3,
    }
    path.write_text(json.dumps(fresh), encoding="utf-8")
    hb = heartbeat_payload(path, stale_s=20.0)
    assert hb["alive"] is True
    assert hb["mode"] == "paper"

    stale = {
        "ts": (datetime.now(UTC) - timedelta(seconds=60)).isoformat(),
        "mode": "paper",
        "ticks": 9,
    }
    path.write_text(json.dumps(stale), encoding="utf-8")
    hb2 = heartbeat_payload(path, stale_s=20.0)
    assert hb2["alive"] is False
    assert hb2["age_s"] is not None and float(hb2["age_s"]) > 20


def test_static_path_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    root.mkdir()
    (root / "style.css").write_text("ok", encoding="utf-8")
    assert _static_file(root, "style.css") is not None
    assert _static_file(root, "../style.css") is None
    assert _static_file(root, "..") is None
    assert _static_file(root, "") is None


def test_api_events_bad_query(tmp_path: Path) -> None:
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    journal = tmp_path / "journal.jsonl"
    journal.write_text('{"event":"boot"}\n', encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/events?after=nope&limit=abc",
            timeout=2,
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["after"] == 0
        assert len(payload["events"]) == 1
        assert payload["next"] == 1

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/health",
            timeout=2,
        ) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        assert health["ok"] is True

        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/static/../index.html",
                timeout=2,
            )
            raise AssertionError("expected 404 for traversal")
        except urllib.error.HTTPError as exc:
            assert exc.code in {400, 404}
    finally:
        server.shutdown()
        server.server_close()


def test_journal_payload_includes_signal_and_has_signal() -> None:
    settings = Settings(min_notional=1_000)
    desk = AgentDesk(settings, RiskGate(settings))
    sig = Signal(
        coin="BTC",
        side="buy",
        imbalance=0.8,
        spread_bps=4.0,
        mid=100.0,
        edge_score=80.0,
        reason="ensemble:imbalance+liquidity",
    )
    decision = DeskDecision(
        "enter",
        side="buy",
        signal=sig,
        reason="agree_2",
        proposals=[
            Proposal("imbalance", "enter", side="buy", confidence=80, signal=sig),
            Proposal("funding", "abstain", reason="funding_mild"),
        ],
        agreeing_agents=["imbalance"],
    )
    payload = desk.journal_payload(decision)
    assert payload["signal"]["mid"] == 100.0
    assert payload["proposals"][0]["has_signal"] is True
    assert payload["proposals"][1]["has_signal"] is False
