"""Radar copy must stay honest about Yahoo fills vs dashes."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RADAR = _ROOT / "frontend" / "app" / "radar" / "page.tsx"
_DETAIL = _ROOT / "frontend" / "app" / "radar" / "[symbol]" / "page.tsx"
_STRIP = _ROOT / "frontend" / "components" / "radar-preview-strip.tsx"


def test_radar_page_mentions_yahoo_fundamentals() -> None:
    text = _RADAR.read_text(encoding="utf-8")
    assert "Yahoo tape + fundamentals" in text
    assert "em dash" in text
    assert "No names on early, ignition, or running lists today." in text


def test_radar_detail_does_not_claim_structure_only() -> None:
    text = _DETAIL.read_text(encoding="utf-8")
    assert "yahoo tape + fundamentals" in text
    assert "fundamentals not scored" not in text


def test_home_strip_mentions_yahoo_fundamentals() -> None:
    text = _STRIP.read_text(encoding="utf-8")
    assert "yahoo tape + fundamentals" in text
    assert "fundamentals not scored" not in text
