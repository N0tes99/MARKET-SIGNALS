from __future__ import annotations

import argparse
import json
import mimetypes
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HEARTBEAT_STALE_S = 20.0


def ui_dir() -> Path:
    # trader_bot/ui next to package root (editable) or beside installed package.
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "ui",  # .../trader_bot/src/hl_scalper -> trader_bot/ui
        here.parent / "ui",
        Path.cwd() / "ui",
    ]
    for path in candidates:
        if (path / "index.html").is_file():
            return path
    raise FileNotFoundError("trader_bot/ui/index.html not found")


def read_jsonl_tail(path: Path, *, after: int = 0, limit: int = 200) -> tuple[list[dict], int]:
    """Return events starting at line index `after`, and the next line cursor.

    Cursor is a 0-based line index (blank / corrupt lines still advance it) so
    clients never re-read the same physical line after a successful poll.
    """
    if after < 0:
        after = 0
    if limit < 1:
        return [], after
    if not path.is_file():
        return [], after
    events: list[dict] = []
    idx = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if idx < after:
                idx += 1
                continue
            raw = line.strip()
            if raw:
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            idx += 1
            if len(events) >= limit:
                break
    return events, idx


def latest_ensemble(path: Path, *, max_scan: int = 4_000) -> dict | None:
    """Find the newest ensemble row by scanning from the end of the journal."""
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0:
        return None

    chunk = min(size, 256 * 1024)
    with path.open("rb") as handle:
        handle.seek(max(0, size - chunk))
        raw = handle.read().decode("utf-8", errors="replace")

    lines = raw.splitlines()
    # If we started mid-line, drop the partial first fragment.
    if size > chunk and lines:
        lines = lines[1:]
    scanned = 0
    for line in reversed(lines):
        scanned += 1
        if scanned > max_scan:
            break
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "ensemble":
            return row
    return None


def journal_stats(path: Path) -> dict[str, float | int]:
    """Single-pass stats without materializing every event."""
    fills = exits = sit = lines = 0
    blocks = kills = ensembles = 0
    wins = losses = 0
    pnl = 0.0
    if not path.is_file():
        return {
            "fills": 0,
            "exits": 0,
            "sit_outs": 0,
            "pnl_usd": 0.0,
            "lines": 0,
            "wins": 0,
            "losses": 0,
            "expectancy": 0.0,
            "blocks": 0,
            "kills": 0,
            "ensembles": 0,
        }
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            lines += 1
            ev = row.get("event")
            if ev == "fill":
                fills += 1
            elif ev == "exit":
                exits += 1
                try:
                    trade_pnl = float(row.get("pnl_usd") or 0)
                except (TypeError, ValueError):
                    trade_pnl = 0.0
                pnl += trade_pnl
                if trade_pnl > 0:
                    wins += 1
                elif trade_pnl < 0:
                    losses += 1
            elif ev == "sit_out":
                sit += 1
            elif ev == "blocked":
                blocks += 1
            elif ev == "kill":
                kills += 1
            elif ev == "ensemble":
                ensembles += 1
    expectancy = (pnl / exits) if exits else 0.0
    return {
        "fills": fills,
        "exits": exits,
        "sit_outs": sit,
        "pnl_usd": pnl,
        "lines": lines,
        "wins": wins,
        "losses": losses,
        "expectancy": expectancy,
        "blocks": blocks,
        "kills": kills,
        "ensembles": ensembles,
    }


def heartbeat_payload(path: Path, *, stale_s: float = HEARTBEAT_STALE_S) -> dict:
    if not path.is_file():
        return {"alive": False}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"alive": False}
    if not isinstance(body, dict):
        return {"alive": False}
    ts_raw = body.get("ts")
    alive = False
    age_s: float | None = None
    if isinstance(ts_raw, str) and ts_raw:
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            age_s = (datetime.now(UTC) - ts.astimezone(UTC)).total_seconds()
            alive = 0.0 <= age_s <= stale_s
        except ValueError:
            alive = False
    out = {"alive": alive, **body}
    if age_s is not None:
        out["age_s"] = round(age_s, 3)
    return out


def _safe_int(values: list[str], default: int) -> int:
    if not values:
        return default
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return default


def _static_file(static_root: Path, rel: str) -> Path | None:
    if not rel or rel.startswith("/") or "\\" in rel or ".." in Path(rel).parts:
        return None
    candidate = (static_root / rel).resolve()
    try:
        candidate.relative_to(static_root.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def make_handler(data_dir: Path) -> type[BaseHTTPRequestHandler]:
    static = ui_dir()
    journal = data_dir / "journal.jsonl"
    heartbeat = data_dir / "heartbeat.json"
    position_path = data_dir / "position.json"
    status_path = data_dir / "status.json"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return  # quiet

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: object) -> None:
            raw = json.dumps(payload, default=str).encode("utf-8")
            self._send(code, raw, "application/json; charset=utf-8")

        def _position(self) -> dict:
            from hl_scalper.ui_state import read_json_file

            body = read_json_file(position_path)
            return body if body is not None else {"open": False}

        def _status(self) -> dict:
            from hl_scalper.ui_state import read_json_file

            body = read_json_file(status_path)
            return body if body is not None else {"mode": None, "armed": False, "killed": False}

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path in {"/", "/index.html"}:
                html = (static / "index.html").read_bytes()
                self._send(200, html, "text/html; charset=utf-8")
                return
            if path.startswith("/static/"):
                rel = path[len("/static/") :]
                file_path = _static_file(static, rel)
                if file_path is None:
                    self._json(404 if rel else 400, {"error": "missing" if rel else "bad_path"})
                    return
                mime, _ = mimetypes.guess_type(str(file_path))
                self._send(200, file_path.read_bytes(), mime or "application/octet-stream")
                return

            if path == "/api/health":
                self._json(200, {"ok": True, "data_dir": str(data_dir)})
                return
            if path == "/api/heartbeat":
                self._json(200, heartbeat_payload(heartbeat))
                return
            if path == "/api/events":
                after = max(0, _safe_int(qs.get("after", ["0"]), 0))
                limit = min(500, max(1, _safe_int(qs.get("limit", ["150"]), 150)))
                events, next_after = read_jsonl_tail(journal, after=after, limit=limit)
                self._json(200, {"after": after, "next": next_after, "events": events})
                return
            if path == "/api/desk":
                ens = latest_ensemble(journal)
                self._json(200, {"ensemble": ens})
                return
            if path == "/api/stats":
                self._json(200, journal_stats(journal))
                return
            if path == "/api/position":
                self._json(200, self._position())
                return
            if path == "/api/status":
                self._json(200, self._status())
                return
            if path == "/api/snapshot":
                after = max(0, _safe_int(qs.get("after", ["0"]), 0))
                limit = min(500, max(1, _safe_int(qs.get("limit", ["120"]), 120)))
                events, next_after = read_jsonl_tail(journal, after=after, limit=limit)
                self._json(
                    200,
                    {
                        "heartbeat": heartbeat_payload(heartbeat),
                        "desk": {"ensemble": latest_ensemble(journal)},
                        "stats": journal_stats(journal),
                        "position": self._position(),
                        "status": self._status(),
                        "events": {"after": after, "next": next_after, "events": events},
                    },
                )
                return

            self._json(404, {"error": "not_found", "path": path})

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pixel agent desk UI (local)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = make_handler(data_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"hl agent desk → http://{args.host}:{args.port}  (data={data_dir})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
