"""Preview copy must stay on the Radar page (no frontend unit runner)."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RADAR = _ROOT / "frontend" / "app" / "radar" / "page.tsx"
_STRIP = _ROOT / "frontend" / "components" / "radar-preview-strip.tsx"


def test_radar_page_is_labeled_preview() -> None:
    text = _RADAR.read_text(encoding="utf-8")
    assert "Preview · structure only" in text
    assert "fundamentals not scored" in text
    assert "No names in early accumulation on tape today." in text


def test_home_strip_is_labeled_preview() -> None:
    text = _STRIP.read_text(encoding="utf-8")
    assert "preview · structure only" in text
    assert "No names in early accumulation on tape today." in text
