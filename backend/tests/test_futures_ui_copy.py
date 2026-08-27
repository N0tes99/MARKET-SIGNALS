"""Futures page is CME / Yahoo continuous, not crypto perps."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FUTURES = _ROOT / "frontend" / "app" / "futures" / "page.tsx"
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_PROXY = _ROOT / "frontend" / "app" / "api" / "backend" / "[...path]" / "route.ts"
_KEEP_WARM = _ROOT / ".github" / "workflows" / "keep-api-warm.yml"


def test_futures_page_is_cme_yahoo() -> None:
    text = _FUTURES.read_text(encoding="utf-8")
    assert 'title="Futures"' in text
    assert "Yahoo Finance continuous front-month" in text
    assert "not a live CME pit" in text
    assert "CFTC COT" in text
    assert "formatCot" in text
    assert "ES=F" in text
    assert "learning from paper" in text
    assert "cme_futures" in text
    assert "fetchPaperSummary" in text
    assert "md:block" in text
    assert "md:hidden" in text
    assert "border-white/[0.06]" in text
    assert "font-mono text-[10px] uppercase tracking-widest" in text
    assert "/assets/" not in text
    assert "funding" not in text.lower()


def test_nav_and_proxy_include_futures() -> None:
    header = _HEADER.read_text(encoding="utf-8")
    assert 'href="/futures"' in header
    proxy = _PROXY.read_text(encoding="utf-8")
    assert "api/v1/futures/board" in proxy


def test_keep_warm_pings_futures_board() -> None:
    text = _KEEP_WARM.read_text(encoding="utf-8")
    # Logs must not print hosts; the echo is generic ("Pinging futures").
    assert "Pinging futures" in text
    assert "Ping futures board" not in text
    assert "/api/v1/futures/board" in text
    assert "X-Cron-Secret" in text
    assert "--max-time 180" in text
    assert text.count("sync=true") >= 2
    # Paper tick must run before the heavy assets rank (Render 502s otherwise).
    paper_at = text.find("POST paper cron-tick")
    assets_at = text.find("Pinging assets")
    assert 0 <= paper_at < assets_at
    assert "3 attempts" in text
