"""Tiny JSON disk cache so in-memory SWR survives process restarts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_json(path: Path) -> Any | None:
    """Load JSON from disk or return None on miss/corruption."""
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed reading disk cache %s", path)
        return None


def write_json(path: Path, payload: Any) -> None:
    """Atomically write JSON to disk (best-effort)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, default=str), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        logger.exception("Failed writing disk cache %s", path)
