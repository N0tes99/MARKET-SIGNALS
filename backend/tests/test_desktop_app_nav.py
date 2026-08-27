"""Installed desktop/PWA window must wrap nav tabs instead of clipping them."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_HOMESCREEN = _ROOT / "frontend" / "components" / "homescreen-provider.tsx"
_CSS = _ROOT / "frontend" / "app" / "globals.css"


def test_desktop_header_stacks_then_wraps_tabs() -> None:
    header = _HEADER.read_text(encoding="utf-8")
    assert "md:flex-nowrap" not in header
    assert "md:overflow-x-auto" not in header
    assert "flex-col gap-2" in header
    assert "xl:flex-row" in header
    assert "Installed desktop PWAs" in header
    assert "flex-wrap items-center" in header


def test_standalone_detects_windows_app_display_modes() -> None:
    text = _HOMESCREEN.read_text(encoding="utf-8")
    assert "window-controls-overlay" in text
    assert "minimal-ui" in text
    css = _CSS.read_text(encoding="utf-8")
    assert "overflow-x: clip" in css
