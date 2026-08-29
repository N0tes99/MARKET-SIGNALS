"""Radar copy must stay honest about Yahoo fills vs dashes."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RADAR = _ROOT / "frontend" / "app" / "radar" / "page.tsx"
_DETAIL = _ROOT / "frontend" / "app" / "radar" / "[symbol]" / "page.tsx"
_STRIP = _ROOT / "frontend" / "components" / "radar-preview-strip.tsx"
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_MANIFEST = _ROOT / "frontend" / "app" / "manifest.ts"
_PROXY = _ROOT / "frontend" / "app" / "api" / "backend" / "[...path]" / "route.ts"
_PWA_GEN = _ROOT / "frontend" / "scripts" / "gen_pwa_icons.py"


def test_radar_page_mentions_yahoo_fundamentals() -> None:
    text = _RADAR.read_text(encoding="utf-8")
    assert "Yahoo tape + fundamentals + SEC 8-K" in text
    assert "Discovery gap is followership vs valuation" in text
    assert "EPS surprise when Yahoo has a print" in text
    assert "em dash" in text
    assert "No names on early, ignition, or running lists today." in text
    assert "fundamentals_filled" in text
    assert "yahoo" in text
    assert "md:block" in text
    assert "equities" in text
    assert "Watch" in text
    assert "Crowded" in text
    assert "perp-v2 universe" in text
    assert "Crypto" in text
    assert 'crypto: "Crypto"' in text
    assert "learning from paper" in text
    assert "Lists can fill when Yahoo fundamentals exist" in text
    assert "Preview — not orders" in text
    assert ">Opp<" in text
    assert "StageRail" in text
    assert "opp {c.scores.runner_score" in text
    assert 'study: "Study"' in text
    assert "Structure-tape replay on truncated daily bars" in text
    assert "that would look ahead" in text
    assert "Dated 8-K filing dates" in text
    assert "lagged Yahoo quarterlies" in text
    assert "13F EDGAR search" in text
    assert "not a complete manager universe" in text
    assert "Live Yahoo info" in text
    assert "Lead 2×" in text
    assert "precision" in text
    assert "5× fpr" in text
    assert "out-of-sample" in text.lower()
    assert "famous" in text.lower()
    assert "structure-only baseline" in text
    assert "not applied to live" in text
    assert "Baseline vs tuned" in text


def test_radar_detail_does_not_claim_structure_only() -> None:
    text = _DETAIL.read_text(encoding="utf-8")
    assert "yahoo tape + fundamentals + sec 8-k · discovery vs valuation" in text
    assert "fundamentals not scored" not in text
    assert "runner failure" in text
    assert "stage" in text
    assert "StageRail" in text
    assert "opp {c.scores.runner_score" in text
    assert "preview" in text
    assert "not orders" in text


def test_compact_header_stacks_on_mobile() -> None:
    text = _HEADER.read_text(encoding="utf-8")
    assert "flex-col" in text
    assert "{title}" in text
    assert "hidden md:block" in text
    assert "h-14" in text


def test_homescreen_allows_desktop_orientation() -> None:
    text = _MANIFEST.read_text(encoding="utf-8")
    assert 'orientation: "any"' in text
    assert "portrait-primary" not in text


def test_homescreen_shortcuts_include_radar_and_tape() -> None:
    text = _MANIFEST.read_text(encoding="utf-8")
    assert 'url: "/radar"' in text
    assert 'url: "/tape"' in text
    assert 'url: "/perps"' in text


def test_proxy_gives_radar_and_tape_long_timeout() -> None:
    text = _PROXY.read_text(encoding="utf-8")
    assert "api/v1/runners" in text
    assert "api/v1/runners/lists" in text
    assert "api/v1/runners/crypto" in text
    assert "api/v1/runners/backtest" in text
    assert "api/v1/runners/tune" in text
    assert "api/v1/options-tape" in text
    assert "api/v1/perps/board" in text
    assert "api/v1/futures/board" in text
    assert "100_000" in text


def test_legacy_pwa_script_uses_signal_mark() -> None:
    text = _PWA_GEN.read_text(encoding="utf-8")
    assert "render_app_icons" in text
    assert 'text = "SE"' not in text


def test_stage_rail_covers_all_stages() -> None:
    text = (_ROOT / "frontend" / "components" / "stage-rail.tsx").read_text(encoding="utf-8")
    assert "dormant" in text
    assert "fundamental_inflection" in text
    assert "early_accumulation" in text
    assert "catalyst" in text
    assert "ignition" in text
    assert "discovery" in text
    assert "momentum" in text
    assert "extended" in text
    assert "compact" in text


def test_home_strip_mentions_yahoo_fundamentals() -> None:
    text = _STRIP.read_text(encoding="utf-8")
    assert "yahoo tape + fundamentals + sec 8-k · discovery vs valuation" in text
    assert "fundamentals not scored" not in text
    assert "fundamentals_filled" in text
    assert "opp {c.scores.runner_score" in text
    assert "preview" in text
    assert "not orders" in text
