from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class JournalEvent:
    event: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {"ts": utc_now_iso(), "event": self.event, **self.payload}


class Journal:
    """Append-only JSONL. Flush + fsync so crashes keep the last line."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **payload: Any) -> None:
        row = JournalEvent(event=event, payload=dict(payload)).to_row()
        line = json.dumps(row, default=str) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def write_mapping(self, row: Mapping[str, Any]) -> None:
        event = str(row.get("event", "unknown"))
        payload = {k: v for k, v in row.items() if k not in {"event", "ts"}}
        self.write(event, **payload)


class Heartbeat:
    """Touch a small JSON file each successful tick for systemd / monitoring."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def beat(self, *, mode: str, coins: tuple[str, ...], extra: dict[str, Any] | None = None) -> None:
        body = {
            "ts": utc_now_iso(),
            "mode": mode,
            "coins": list(coins),
            **(extra or {}),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(body, default=str) + "\n", encoding="utf-8")
        tmp.replace(self.path)


def dump_dataclass(obj: object) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)  # type: ignore[arg-type]
    return dict(obj)  # type: ignore[arg-type]
