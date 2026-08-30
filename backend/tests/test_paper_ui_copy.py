"""Paper card shows paused new-open factories."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PANEL = _ROOT / "frontend" / "components" / "paper-agent-panel.tsx"


def test_paper_panel_shows_paused_new_opens() -> None:
    text = _PANEL.read_text(encoding="utf-8")
    assert "paused_new_opens" in text
    assert "perp v2 sleeve" in text
    assert "new opens paused" in text
    assert "tick_stale" in text
    assert "tick stale — leftover opens still manage" in text
