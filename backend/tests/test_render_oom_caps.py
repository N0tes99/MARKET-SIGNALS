"""Dashboard load must not stampede Render's 512MB web dyno."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_start_script_caps_malloc_arenas() -> None:
    text = (_ROOT / "backend" / "start.sh").read_text(encoding="utf-8")
    assert "MALLOC_ARENA_MAX" in text
    dockerfile = (_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "MALLOC_ARENA_MAX=2" in dockerfile


def test_scan_pools_stay_small() -> None:
    from app.core.process_limits import (
        OHLCV_WARM_WORKERS,
        RANK_EVAL_WORKERS,
        SCAN_WORKERS,
    )

    assert OHLCV_WARM_WORKERS <= 4
    assert RANK_EVAL_WORKERS <= 4
    assert SCAN_WORKERS <= 3


def test_home_defers_heavy_feeds_after_rank_all() -> None:
    feeds = (
        _ROOT / "frontend" / "components" / "deferred-dashboard-feeds.tsx"
    ).read_text(encoding="utf-8")
    assert "delayMs={8_000}" in feeds
    panel = (_ROOT / "frontend" / "components" / "paper-agent-panel.tsx").read_text(
        encoding="utf-8"
    )
    assert "timeout: 8_000" in panel
    assert "8_000" in panel.split("setTimeout")[1]
