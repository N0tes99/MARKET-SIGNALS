"""Admin env dark-state — booleans only, no secret values."""

import pytest
from httpx import AsyncClient

from app.core.site_gate import access_health


def test_access_health_strip_dark_by_default(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.reddit_client_id", "")
    monkeypatch.setattr("app.config.settings.reddit_client_secret", "")
    monkeypatch.setattr("app.config.settings.fred_api_key", "")
    monkeypatch.setattr("app.config.settings.gemini_api_key", "")
    monkeypatch.setattr("app.config.settings.alert_enabled", False)
    monkeypatch.setattr("app.config.settings.cron_secret", "")
    monkeypatch.setattr("app.config.settings.alert_discord_bot_token", "")
    monkeypatch.setattr("app.config.settings.alert_discord_channel_id", "")
    monkeypatch.setattr("app.config.settings.alert_discord_webhook_url", "")
    payload = access_health()
    assert payload.reddit is False
    assert payload.fred is False
    assert payload.discord is False
    assert "reddit dark" in payload.strip
    assert "cron off" in payload.strip
    assert "discord dark" in payload.strip


def test_access_health_set_flags(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.reddit_client_id", "id")
    monkeypatch.setattr("app.config.settings.reddit_client_secret", "sec")
    monkeypatch.setattr("app.config.settings.fred_api_key", "fred")
    monkeypatch.setattr("app.config.settings.gemini_api_key", "gem")
    monkeypatch.setattr("app.config.settings.alert_enabled", True)
    monkeypatch.setattr("app.config.settings.cron_secret", "cron")
    monkeypatch.setattr("app.config.settings.alert_discord_webhook_url", "https://discord.example/hook")
    payload = access_health()
    assert payload.reddit is True
    assert payload.fred is True
    assert payload.gemini is True
    assert payload.discord is True
    assert payload.alert_enabled is True
    assert payload.cron_secret is True
    assert payload.strip == "reddit set · fred set · gemini set · discord on · cron on"


@pytest.mark.asyncio
async def test_access_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/access/health")
    assert response.status_code == 200
    data = response.json()
    assert "strip" in data
    assert set(data) >= {
        "reddit",
        "fred",
        "gemini",
        "discord",
        "alert_enabled",
        "cron_secret",
        "strip",
    }
    assert not any("sk-" in str(v) for v in data.values())
