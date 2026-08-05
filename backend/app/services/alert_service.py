"""Alert service — notify when confidence/grade crosses thresholds."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from threading import Lock

import httpx

from app.config import settings
from app.schemas.assets import AssetSummary

logger = logging.getLogger(__name__)

_GRADE_RANK: dict[str, int] = {
    "F": 0,
    "D": 1,
    "C": 2,
    "B": 3,
    "A": 4,
    "A+": 5,
}


@dataclass
class AlertEvent:
    """A single crossed-threshold alert candidate."""

    symbol: str
    confidence: float
    trade_grade: str
    trade_state: str
    execution_signal: str
    expected_value: float
    trend: str
    asset_class: str


@dataclass
class AlertDispatchResult:
    """Outcome of evaluating and sending alerts."""

    enabled: bool
    evaluated: int
    matched: int
    sent: int
    skipped_cooldown: int
    discord_ok: bool | None
    email_ok: bool | None
    events: list[AlertEvent]


def grade_meets_minimum(grade: str, minimum: str) -> bool:
    """Return True if trade grade is at least the configured minimum."""
    return _GRADE_RANK.get(grade.upper(), -1) >= _GRADE_RANK.get(minimum.upper(), 99)


def format_alert_text(event: AlertEvent) -> str:
    """Plain-text body for email / logs."""
    return (
        f"Signal Engine alert: {event.symbol}\n"
        f"Confidence: {event.confidence:.1f}%\n"
        f"Grade: {event.trade_grade}\n"
        f"State: {event.trade_state} · Signal: {event.execution_signal}\n"
        f"Trend: {event.trend} · EV: {event.expected_value:.2f}\n"
        f"Class: {event.asset_class}"
    )


class AlertService:
    """Evaluates asset summaries and dispatches Discord + email alerts."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_sent: dict[str, datetime] = {}

    @property
    def enabled(self) -> bool:
        return bool(settings.alert_enabled)

    @staticmethod
    def discord_configured() -> bool:
        """True when bot token+channel or a webhook URL is set."""
        bot_ready = bool(
            settings.alert_discord_bot_token.strip()
            and settings.alert_discord_channel_id.strip()
        )
        return bot_ready or bool(settings.alert_discord_webhook_url.strip())

    def status(self) -> dict:
        """Return current alert configuration (no secrets)."""
        bot_ready = bool(
            settings.alert_discord_bot_token.strip()
            and settings.alert_discord_channel_id.strip()
        )
        webhook_ready = bool(settings.alert_discord_webhook_url.strip())
        if bot_ready and webhook_ready:
            discord_mode = "both"
        elif bot_ready:
            discord_mode = "bot"
        elif webhook_ready:
            discord_mode = "webhook"
        else:
            discord_mode = "none"
        return {
            "enabled": self.enabled,
            "min_confidence": settings.alert_min_confidence,
            "min_grade": settings.alert_min_grade,
            "cooldown_minutes": settings.alert_cooldown_minutes,
            "discord_configured": self.discord_configured(),
            "discord_mode": discord_mode,
            "email_configured": bool(
                settings.alert_email_to.strip()
                and settings.alert_smtp_host.strip()
                and settings.alert_smtp_user.strip()
            ),
            "channels": {
                "discord": self.discord_configured(),
                "email": bool(settings.alert_email_to.strip() and settings.alert_smtp_host.strip()),
            },
        }

    @staticmethod
    def _discord_embed(event: AlertEvent) -> dict:
        """Build a Discord embed payload for an alert event."""
        color = 0x8FA88A if event.confidence >= 70 else 0x9A958D
        return {
            "title": f"{event.symbol} — grade {event.trade_grade}",
            "description": (
                f"**{event.confidence:.0f}%** confidence · "
                f"{event.trade_state} / {event.execution_signal}"
            ),
            "color": color,
            "fields": [
                {"name": "Trend", "value": event.trend, "inline": True},
                {"name": "EV", "value": f"{event.expected_value:.2f}", "inline": True},
                {"name": "Class", "value": event.asset_class, "inline": True},
            ],
            "footer": {"text": "Signal Engine alert"},
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def evaluate(self, assets: list[AssetSummary]) -> list[AlertEvent]:
        """Filter assets that meet confidence + grade thresholds."""
        matches: list[AlertEvent] = []
        for asset in assets:
            if asset.confidence < settings.alert_min_confidence:
                continue
            if not grade_meets_minimum(asset.trade_grade, settings.alert_min_grade):
                continue
            matches.append(
                AlertEvent(
                    symbol=asset.symbol,
                    confidence=asset.confidence,
                    trade_grade=asset.trade_grade,
                    trade_state=asset.trade_state,
                    execution_signal=asset.execution_signal,
                    expected_value=asset.expected_value,
                    trend=asset.trend,
                    asset_class=asset.asset_class,
                )
            )
        return matches

    def _cooldown_active(self, symbol: str) -> bool:
        last = self._last_sent.get(symbol.upper())
        if last is None:
            return False
        return datetime.now(UTC) - last < timedelta(minutes=settings.alert_cooldown_minutes)

    def _mark_sent(self, symbol: str) -> None:
        self._last_sent[symbol.upper()] = datetime.now(UTC)

    def send_discord(self, event: AlertEvent) -> bool:
        """Post an embed via Discord bot and/or webhook (both if configured)."""
        embed = self._discord_embed(event)
        token = settings.alert_discord_bot_token.strip()
        channel_id = settings.alert_discord_channel_id.strip()
        webhook = settings.alert_discord_webhook_url.strip()

        attempts = 0
        successes = 0

        if token and channel_id:
            attempts += 1
            if self._send_discord_bot(event.symbol, token, channel_id, embed):
                successes += 1

        if webhook:
            attempts += 1
            if self._send_discord_webhook(event.symbol, webhook, embed):
                successes += 1

        return attempts > 0 and successes > 0

    def _send_discord_bot(
        self,
        symbol: str,
        token: str,
        channel_id: str,
        embed: dict,
    ) -> bool:
        """Send a channel message as our Discord application bot."""
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }
        payload = {"embeds": [embed]}
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            return True
        except Exception:
            logger.exception("Discord bot alert failed for %s", symbol)
            return False

    def _send_discord_webhook(self, symbol: str, url: str, embed: dict) -> bool:
        """Fallback: post embed to a Discord webhook URL."""
        payload = {"username": "Signal Engine", "embeds": [embed]}
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
            return True
        except Exception:
            logger.exception("Discord webhook alert failed for %s", symbol)
            return False

    def send_email(self, event: AlertEvent) -> bool:
        """Send alert email via SMTP."""
        to_addr = settings.alert_email_to.strip()
        host = settings.alert_smtp_host.strip()
        user = settings.alert_smtp_user.strip()
        password = settings.alert_smtp_password
        if not (to_addr and host and user):
            return False

        msg = EmailMessage()
        msg["Subject"] = f"[Signal Engine] {event.symbol} {event.trade_grade} @ {event.confidence:.0f}%"
        msg["From"] = settings.alert_email_from.strip() or user
        msg["To"] = to_addr
        msg.set_content(format_alert_text(event))

        try:
            if settings.alert_smtp_use_tls:
                with smtplib.SMTP(host, settings.alert_smtp_port, timeout=15) as server:
                    server.starttls()
                    server.login(user, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP_SSL(host, settings.alert_smtp_port, timeout=15) as server:
                    server.login(user, password)
                    server.send_message(msg)
            return True
        except Exception:
            logger.exception("Email alert failed for %s", event.symbol)
            return False

    def dispatch(self, assets: list[AssetSummary], *, force: bool = False) -> AlertDispatchResult:
        """Evaluate assets and send alerts for new crosses."""
        if not self.enabled and not force:
            return AlertDispatchResult(
                enabled=False,
                evaluated=len(assets),
                matched=0,
                sent=0,
                skipped_cooldown=0,
                discord_ok=None,
                email_ok=None,
                events=[],
            )

        matches = self.evaluate(assets)
        sent = 0
        skipped = 0
        fired: list[AlertEvent] = []
        discord_ok: bool | None = None
        email_ok: bool | None = None

        with self._lock:
            for event in matches:
                if not force and self._cooldown_active(event.symbol):
                    skipped += 1
                    continue

                channel_hit = False
                if self.discord_configured():
                    d_ok = self.send_discord(event)
                    discord_ok = (discord_ok is True) or d_ok
                    channel_hit = channel_hit or d_ok
                if (
                    settings.alert_email_to.strip()
                    and settings.alert_smtp_host.strip()
                    and settings.alert_smtp_user.strip()
                ):
                    e_ok = self.send_email(event)
                    email_ok = (email_ok is True) or e_ok
                    channel_hit = channel_hit or e_ok

                if channel_hit:
                    self._mark_sent(event.symbol)
                    sent += 1
                    fired.append(event)
                elif not (
                    self.discord_configured()
                    or (
                        settings.alert_email_to.strip()
                        and settings.alert_smtp_host.strip()
                    )
                ):
                    logger.warning(
                        "Alert matched %s but no Discord/email channel is configured",
                        event.symbol,
                    )

        return AlertDispatchResult(
            enabled=self.enabled or force,
            evaluated=len(assets),
            matched=len(matches),
            sent=sent,
            skipped_cooldown=skipped,
            discord_ok=discord_ok,
            email_ok=email_ok,
            events=fired,
        )

    def send_test(self, channel: str = "both") -> dict[str, bool | str]:
        """Send a test alert to configured channels."""
        event = AlertEvent(
            symbol="TEST",
            confidence=72.0,
            trade_grade="B",
            trade_state="WATCH",
            execution_signal="WATCH",
            expected_value=0.42,
            trend="Bullish",
            asset_class="etf",
        )
        result: dict[str, bool | str] = {"symbol": "TEST"}
        if channel in {"both", "discord"}:
            result["discord"] = self.send_discord(event) if self.discord_configured() else False
            result["discord_mode"] = self.status()["discord_mode"]
        if channel in {"both", "email"}:
            result["email"] = (
                self.send_email(event)
                if (
                    settings.alert_email_to.strip()
                    and settings.alert_smtp_host.strip()
                    and settings.alert_smtp_user.strip()
                )
                else False
            )
        return result
