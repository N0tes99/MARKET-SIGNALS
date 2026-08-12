"""Deeper analysis may hit Yahoo earnings; rank/dashboard path must not."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_analysis_route_requests_earnings() -> None:
    text = (_ROOT / "app" / "api" / "routes" / "analysis.py").read_text(encoding="utf-8")
    assert "include_earnings=True" in text


def test_rank_event_path_skips_earnings() -> None:
    text = (_ROOT / "app" / "engines" / "event_engine" / "engine.py").read_text(
        encoding="utf-8"
    )
    assert "include_earnings=False" in text
    assert "earnings deferred" in text
