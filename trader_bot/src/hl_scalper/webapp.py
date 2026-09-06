from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


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
    if not path.is_file():
        return [], after
    events: list[dict] = []
    idx = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if idx < after:
                idx += 1
                continue
            line = line.strip()
            if not line:
                idx += 1
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
            idx += 1
            if len(events) >= limit:
                break
    return events, after + len(events)


def latest_ensemble(path: Path) -> dict | None:
    events, _ = read_jsonl_tail(path, after=0, limit=50_000)
    for row in reversed(events):
        if row.get("event") == "ensemble":
            return row
    return None


def make_handler(data_dir: Path) -> type[BaseHTTPRequestHandler]:
    static = ui_dir()
    journal = data_dir / "journal.jsonl"
    heartbeat = data_dir / "heartbeat.json"

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
                if ".." in rel or rel.startswith("/"):
                    self._json(400, {"error": "bad_path"})
                    return
                file_path = static / rel
                if not file_path.is_file():
                    self._json(404, {"error": "missing"})
                    return
                mime, _ = mimetypes.guess_type(str(file_path))
                self._send(200, file_path.read_bytes(), mime or "application/octet-stream")
                return

            if path == "/api/health":
                self._json(200, {"ok": True, "data_dir": str(data_dir)})
                return
            if path == "/api/heartbeat":
                if not heartbeat.is_file():
                    self._json(200, {"alive": False})
                    return
                try:
                    body = json.loads(heartbeat.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    self._json(200, {"alive": False})
                    return
                self._json(200, {"alive": True, **body})
                return
            if path == "/api/events":
                after = int(qs.get("after", ["0"])[0] or 0)
                limit = min(500, int(qs.get("limit", ["150"])[0] or 150))
                events, next_after = read_jsonl_tail(journal, after=after, limit=limit)
                self._json(200, {"after": after, "next": next_after, "events": events})
                return
            if path == "/api/desk":
                ens = latest_ensemble(journal)
                self._json(200, {"ensemble": ens})
                return
            if path == "/api/stats":
                events, _ = read_jsonl_tail(journal, after=0, limit=50_000)
                fills = sum(1 for e in events if e.get("event") == "fill")
                exits = sum(1 for e in events if e.get("event") == "exit")
                sit = sum(1 for e in events if e.get("event") == "sit_out")
                pnl = sum(float(e.get("pnl_usd") or 0) for e in events if e.get("event") == "exit")
                self._json(
                    200,
                    {
                        "fills": fills,
                        "exits": exits,
                        "sit_outs": sit,
                        "pnl_usd": pnl,
                        "lines": len(events),
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
