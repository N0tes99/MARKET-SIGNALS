"""Perps tab must expose paper crypto activity, funding, and honest liq states."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PERPS = _ROOT / "frontend" / "app" / "perps" / "page.tsx"
_HEADER = _ROOT / "frontend" / "components" / "site-header.tsx"
_MANIFEST = _ROOT / "frontend" / "app" / "manifest.ts"
_PROXY = _ROOT / "frontend" / "app" / "api" / "backend" / "[...path]" / "route.ts"


def test_perps_page_sections() -> None:
    text = _PERPS.read_text(encoding="utf-8")
    assert "Crypto perps" in text
    assert "Paper activity" in text
    assert "Funding board" in text
    assert "Liquidations" in text
    assert "Perp ideas" in text
    assert "crypto_perp_v2" in text
    assert "paused_new_opens" in text
    assert "new Layer-2 crypto_setup opens paused" in text
    assert "Coinglass" in text
    assert "OKX" in text
    assert "need a Coinglass key" not in text
    assert "md:block" in text
    assert "Not live exchange orders" in text


def test_nav_and_manifest_include_perps() -> None:
    header = _HEADER.read_text(encoding="utf-8")
    assert 'href="/perps"' in header
    assert 'href="/futures"' in header
    assert "Futures" in header
    manifest = _MANIFEST.read_text(encoding="utf-8")
    assert 'url: "/perps"' in manifest


def test_proxy_gives_perps_board_long_timeout() -> None:
    text = _PROXY.read_text(encoding="utf-8")
    assert "api/v1/perps/board" in text
    assert "api/v1/futures/board" in text
    assert "100_000" in text
    assert "x-forwarded-for" in text
    assert "x-nf-client-connection-ip" in text
