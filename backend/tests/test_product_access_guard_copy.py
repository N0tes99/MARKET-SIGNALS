"""Product access guard must not skip admin pages or fail open."""

from pathlib import Path

_GUARD = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "components"
    / "product-access-guard.tsx"
)


def test_admin_pages_are_not_client_gate_bypass() -> None:
    text = _GUARD.read_text(encoding="utf-8")
    assert '"/admin/access"' not in text
    assert '"/admin/wallets"' not in text
    assert '"/admin/api-access"' not in text
    assert "Access check failed" in text
    assert "return <>{children}</>" not in text.split("gateQuery.isError")[1]
