"""Tape page must expose the open-universe extra-ticker hunt."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TAPE = _ROOT / "frontend" / "app" / "tape" / "page.tsx"


def test_tape_page_has_extra_ticker_hunt() -> None:
    text = _TAPE.read_text(encoding="utf-8")
    assert "Hunt a ticker" in text
    assert "se_tape_extras" not in text
    assert "normalizeTapeTicker" in text
