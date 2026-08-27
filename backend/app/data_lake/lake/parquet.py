"""Dump warehouse OHLCV to parquet. No-op when empty or path unset."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.data_lake.warehouse.ohlcv import bars_to_frame, get_bars, list_series

logger = logging.getLogger(__name__)


def _root() -> Path | None:
    raw = (settings.data_lake_path or "").strip()
    if not raw:
        return None
    return Path(raw)


def export_series(symbol: str, timeframe: str, *, root: Path | None = None) -> Path | None:
    """Write one symbol/timeframe. Returns path or None when there are no bars."""
    dest_root = root if root is not None else _root()
    if dest_root is None:
        return None
    bars = get_bars(symbol, timeframe, limit=5_000)
    if not bars:
        return None
    frame = bars_to_frame(bars)
    path = dest_root / symbol.upper() / f"{timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def export_warehouse(*, root: Path | None = None) -> dict[str, object]:
    """Export every warehouse series. Refuses an empty lake."""
    dest_root = root if root is not None else _root()
    if dest_root is None:
        return {"exported": 0, "reason": "disabled", "files": []}
    series = list_series()
    if not series:
        return {"exported": 0, "reason": "empty", "files": []}
    files: list[str] = []
    for symbol, timeframe in series:
        path = export_series(symbol, timeframe, root=dest_root)
        if path is not None:
            files.append(str(path))
    if not files:
        return {"exported": 0, "reason": "empty", "files": []}
    return {"exported": len(files), "reason": "ok", "files": files}
