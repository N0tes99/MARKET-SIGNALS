"""Radar copy must stay honest about Yahoo fills vs dashes."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RADAR = _ROOT / "frontend" / "app" / "radar" / "page.tsx"
_DETAIL = _ROOT / "frontend" / "app" / "radar" / "[symbol]" / "page.tsx"
_STRIP = _ROOT / "frontend" / "components" / "radar-preview-strip.tsx"
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_MANIFEST = _ROOT / "frontend" / "app" / "manifest.ts"


def test_radar_page_mentions_yahoo_fundamentals() -> None:
    text = _RADAR.read_text(encoding="utf-8")
    assert "Yahoo tape + fundamentals" in text
    assert "em dash" in text
    assert "No names on early, ignition, or running lists today." in text
    assert "fundamentals_filled" in text
    assert "yahoo" in text
    assert "hidden md:block" in text


def test_radar_detail_does_not_claim_structure_only() -> None:
    text = _DETAIL.read_text(encoding="utf-8")
    assert "yahoo tape + fundamentals" in text
    assert "fundamentals not scored" not in text
    assert "runner failure" in text
    assert "stage" in text


def test_compact_header_stacks_on_mobile() -> None:
    text = _HEADER.read_text(encoding="utf-8")
    assert "flex-col" in text
    assert "{title}" in text


def test_homescreen_shortcuts_include_radar_and_tape() -> None:
    text = _MANIFEST.read_text(encoding="utf-8")
    assert 'url: "/radar"' in text
    assert 'url: "/tape"' in text


def test_home_strip_mentions_yahoo_fundamentals() -> None:
    text = _STRIP.read_text(encoding="utf-8")
    assert "yahoo tape + fundamentals" in text
    assert "fundamentals not scored" not in text
    assert "fundamentals_filled" in text
