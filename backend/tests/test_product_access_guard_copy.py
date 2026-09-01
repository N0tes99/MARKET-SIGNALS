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
    assert "warming up" in text
    assert "gateQuery.refetch()" in text
    assert "return <>{children}</>" not in text.split("gateQuery.isError")[1]


def test_session_probe_waits_for_render_cold_start() -> None:
    api = (
        Path(__file__).resolve().parents[2] / "frontend" / "services" / "api.ts"
    ).read_text(encoding="utf-8")
    me = api.split("export async function fetchMe")[1].split("export async function registerAccount")[0]
    assert "DEFAULT_FETCH_TIMEOUT_MS" in me
    assert "8_000" not in me
    assert "127.0.0.1:8000" not in me
    assert "warming up" in me
    gate = api.split("export async function fetchGateStatus")[1].split("export async function verifySiteGate")[0]
    assert "8_000" not in gate
