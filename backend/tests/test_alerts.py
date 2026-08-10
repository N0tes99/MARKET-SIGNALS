"""Alert threshold and dispatch tests."""

from datetime import UTC, datetime, timedelta

from app.schemas.assets import AssetSummary
from app.services.alert_service import (
    AlertEvent,
    AlertService,
    grade_meets_minimum,
)


def _asset(**kwargs) -> AssetSummary:
    base = {
        "symbol": "SPY",
        "confidence": 68.0,
        "trend": "Bullish",
        "trade_grade": "B",
        "buyer_strength": 60.0,
        "risk": 50.0,
        "expected_value": 0.4,
        "trade_state": "WATCH",
        "execution_signal": "WATCH",
        "asset_class": "etf",
    }
    base.update(kwargs)
    return AssetSummary(**base)


def _event(**kwargs) -> AlertEvent:
    base = {
        "symbol": "SPY",
        "confidence": 68.0,
        "trade_grade": "B",
        "trade_state": "WATCH",
        "execution_signal": "WATCH",
        "expected_value": 0.4,
        "trend": "Bullish",
        "asset_class": "etf",
    }
    base.update(kwargs)
    return AlertEvent(**base)


def test_grade_meets_minimum() -> None:
    assert grade_meets_minimum("B", "B")
    assert grade_meets_minimum("A", "B")
    assert grade_meets_minimum("A+", "B")
    assert not grade_meets_minimum("C", "B")
    assert not grade_meets_minimum("F", "B")


def test_evaluate_filters_threshold() -> None:
    service = AlertService()
    matches = service.evaluate(
        [
            _asset(symbol="SPY", confidence=68, trade_grade="B"),
            _asset(symbol="QQQ", confidence=50, trade_grade="A"),
            _asset(symbol="AAPL", confidence=80, trade_grade="C"),
        ]
    )
    symbols = {m.symbol for m in matches}
    assert "SPY" in symbols
    assert "QQQ" not in symbols  # confidence too low
    assert "AAPL" not in symbols  # grade too low


def test_cooldown_skips_second_send(monkeypatch) -> None:
    service = AlertService()
    monkeypatch.setattr("app.services.alert_service.settings.alert_enabled", True)
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_bot_token", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_channel_id", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_webhook_url", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_email_to", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_smtp_host", "")

    assets = [_asset()]
    first = service.dispatch(assets)
    # no channels configured => sent 0, but evaluate matched
    assert first.matched == 1

    # Mark as sent manually then ensure cooldown skips
    service._mark_sent(_event())
    monkeypatch.setattr(
        "app.services.alert_service.settings.alert_discord_webhook_url",
        "https://discord.test/webhook",
    )
    sent_calls: list[str] = []

    def fake_discord(event):
        sent_calls.append(event.symbol)
        return True

    monkeypatch.setattr(service, "send_discord", fake_discord)
    second = service.dispatch(assets)
    assert second.skipped_cooldown == 1
    assert sent_calls == []


def test_unchanged_hot_skips_after_cooldown(monkeypatch) -> None:
    """Same grade/conf after cooldown should not spam Discord."""
    service = AlertService()
    monkeypatch.setattr("app.services.alert_service.settings.alert_enabled", True)
    monkeypatch.setattr("app.services.alert_service.settings.alert_cooldown_minutes", 1)
    monkeypatch.setattr(
        "app.services.alert_service.settings.alert_discord_webhook_url",
        "https://discord.test/webhook",
    )
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_bot_token", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_channel_id", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_email_to", "")

    sent: list[str] = []
    monkeypatch.setattr(service, "send_discord", lambda e: sent.append(e.trigger) or True)

    assets = [_asset(confidence=70, trade_grade="B", trend="Bullish")]
    first = service.dispatch(assets)
    assert first.sent == 1
    assert sent == ["threshold_cross"]
    assert "Ref" in service._discord_embed(first.events[0])["fields"][-1]["name"]

    # Expire cooldown but keep snapshot identical
    service._last_sent["SPY"] = datetime.now(UTC) - timedelta(minutes=5)
    second = service.dispatch(assets)
    assert second.sent == 0
    assert second.skipped_unchanged == 1
    assert sent == ["threshold_cross"]


def test_material_confidence_up_refires(monkeypatch) -> None:
    service = AlertService()
    monkeypatch.setattr("app.services.alert_service.settings.alert_enabled", True)
    monkeypatch.setattr("app.services.alert_service.settings.alert_cooldown_minutes", 1)
    monkeypatch.setattr(
        "app.services.alert_service.settings.alert_discord_webhook_url",
        "https://discord.test/webhook",
    )
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_bot_token", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_discord_channel_id", "")
    monkeypatch.setattr("app.services.alert_service.settings.alert_email_to", "")

    triggers: list[str] = []
    refs: list[str] = []

    def fake_discord(event: AlertEvent) -> bool:
        triggers.append(event.trigger)
        refs.append(event.trigger_ref)
        return True

    monkeypatch.setattr(service, "send_discord", fake_discord)

    service.dispatch([_asset(confidence=68, trade_grade="B")])
    service._last_sent["SPY"] = datetime.now(UTC) - timedelta(minutes=5)
    service.dispatch([_asset(confidence=75, trade_grade="B")])

    assert triggers == ["threshold_cross", "confidence_up"]
    assert "68%" in refs[1] and "75%" in refs[1]


def test_send_discord_prefers_bot_over_webhook(monkeypatch) -> None:
    service = AlertService()
    monkeypatch.setattr(
        "app.services.alert_service.settings.alert_discord_bot_token",
        "bot-token",
    )
    monkeypatch.setattr(
        "app.services.alert_service.settings.alert_discord_channel_id",
        "123456",
    )
    monkeypatch.setattr(
        "app.services.alert_service.settings.alert_discord_webhook_url",
        "https://discord.test/webhook",
    )
    calls: list[str] = []

    monkeypatch.setattr(
        service,
        "_send_discord_bot",
        lambda symbol, token, channel_id, embed: calls.append("bot") or True,
    )
    monkeypatch.setattr(
        service,
        "_send_discord_webhook",
        lambda symbol, url, embed: calls.append("webhook") or True,
    )

    ok = service.send_discord(_event())
    assert ok is True
    assert calls == ["bot"]
    assert service.status()["discord_mode"] == "bot+webhook_fallback"
