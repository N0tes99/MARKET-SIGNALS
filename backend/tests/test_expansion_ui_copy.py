"""Expansion radar UI is wired through the API client and cortex blackboard."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PAGE = _ROOT / "frontend" / "app" / "expansion" / "page.tsx"
_STRIP = _ROOT / "frontend" / "components" / "expansion-preview-strip.tsx"
_CARD = _ROOT / "frontend" / "components" / "asset-expansion-card.tsx"
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_MANIFEST = _ROOT / "frontend" / "app" / "manifest.ts"
_PROXY = _ROOT / "frontend" / "app" / "api" / "backend" / "[...path]" / "route.ts"
_API = _ROOT / "frontend" / "services" / "api.ts"
_DEPS = _ROOT / "backend" / "app" / "core" / "service_dependencies.py"
_ARCH = _ROOT / "ARCHITECTURE.md"


def test_expansion_page_uses_api_client_not_raw_host() -> None:
    text = _PAGE.read_text(encoding="utf-8")
    assert "useExpansionFeed" in text
    assert "useCortexMemory" in text
    assert "NEXT_PUBLIC_API_URL" not in text
    assert "13-category grades" in text
    assert "TRIGGER/EXPANSION" in text


def test_nav_and_manifest_include_expansion() -> None:
    header = _HEADER.read_text(encoding="utf-8")
    assert 'href="/expansion"' in header
    manifest = _MANIFEST.read_text(encoding="utf-8")
    assert 'url: "/expansion"' in manifest


def test_desk_and_asset_surface_expansion() -> None:
    strip = _STRIP.read_text(encoding="utf-8")
    assert "cortex blackboard" in strip
    assert "trigger/expansion only" in strip
    card = _CARD.read_text(encoding="utf-8")
    assert "not a grade override" in card
    assert "useExpansionSymbol" in card
    assert 'data.state !== "dormant"' in card


def test_api_client_and_proxy_cover_cortex() -> None:
    api = _API.read_text(encoding="utf-8")
    assert "fetchExpansionFeed" in api
    assert "fetchCortexMemory" in api
    proxy = _PROXY.read_text(encoding="utf-8")
    assert "api/v1/expansion" in proxy
    assert "api/v1/cortex" in proxy


def test_paper_agent_gets_cortex() -> None:
    text = _DEPS.read_text(encoding="utf-8")
    assert "cortex=get_cortex_orchestrator()" in text


def test_architecture_mentions_expansion_ui() -> None:
    text = _ARCH.read_text(encoding="utf-8")
    assert "No `/expansion` UI" not in text
    assert "`/expansion` radar" in text
