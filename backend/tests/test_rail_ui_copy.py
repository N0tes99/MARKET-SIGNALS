"""Rail nested site is wired as a clerk, not a second desk."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PAGE = _ROOT / "frontend" / "app" / "rail" / "page.tsx"
_LAYOUT = _ROOT / "frontend" / "app" / "rail" / "layout.tsx"
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_RAIL_HEADER = _ROOT / "frontend" / "components" / "rail-header.tsx"
_MANIFEST = _ROOT / "frontend" / "app" / "manifest.ts"
_API = _ROOT / "frontend" / "services" / "api.ts"
_ARCH = _ROOT / "ARCHITECTURE.md"
_PLAN = _ROOT / "docs" / "research" / "rail-execution-surface.md"


def test_rail_page_is_blind_clerk() -> None:
    text = _PAGE.read_text(encoding="utf-8")
    assert "useRailDesk" in text
    assert "Dry-run paper ack" in text
    assert "not live exchange orders" in text
    assert "No trade is a valid decision" in text
    assert "Phase B reads Hyperliquid books" in text
    assert "HIP-4" in text
    assert "Hyperliquid" in text
    assert "Drift" in text
    assert "Polymarket" in text
    assert "NEXT_PUBLIC_API_URL" not in text
    # Clerk cards must not render a ticker field.
    assert "envelope.symbol" not in text
    assert "trade.symbol" not in text


def test_rail_has_nested_chrome() -> None:
    layout = _LAYOUT.read_text(encoding="utf-8")
    assert "RailHeader" in layout
    header = _RAIL_HEADER.read_text(encoding="utf-8")
    assert "← Desk" in header
    assert 'href="/perps"' in header


def test_nav_and_manifest_include_rail() -> None:
    header = _HEADER.read_text(encoding="utf-8")
    assert 'href="/rail"' in header
    manifest = _MANIFEST.read_text(encoding="utf-8")
    assert 'url: "/rail"' in manifest


def test_api_client_covers_rail() -> None:
    api = _API.read_text(encoding="utf-8")
    assert "fetchRailDesk" in api
    assert "/api/v1/rail/desk" in api
    assert "/api/v1/rail/clerk/simulate" in api


def test_architecture_and_plan_exist() -> None:
    arch = _ARCH.read_text(encoding="utf-8")
    assert "### 5.7 Surface 6" in arch
    assert "`/rail`" in arch
    plan = _PLAN.read_text(encoding="utf-8")
    assert "venue-native discovery" in plan
    assert "Hyperliquid is the crypto rail" in plan
    assert "Identify only where we can execute" in arch
