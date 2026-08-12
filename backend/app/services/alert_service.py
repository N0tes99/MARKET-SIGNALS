"""Alert service — notify when confidence/grade crosses thresholds."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock

import httpx

from app.config import settings
from app.schemas.assets import AssetSummary
from app.services.alert_state_store import (
    AlertSnapshot,
    MemoryAlertStateStore,
    PostgresAlertStateStore,
    build_alert_state_store,
)
from app.services.mailer import send_mail, smtp_configured

logger = logging.getLogger(__name__)

_GRADE_RANK: dict[str, int] = {
    "F": 0,
    "D": 1,
    "C": 2,
    "B": 3,
    "A": 4,
    "A+": 5,
}

# Re-alert after cooldown only if the case moved meaningfully
_MIN_CONFIDENCE_DELTA = 5.0


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
    # Why this fire happened + compact human ref for Discord/email
    trigger: str = "threshold_cross"
    trigger_ref: str = ""
    prev_confidence: float | None = None
    prev_grade: str | None = None


@dataclass
class AlertDispatchResult:
    """Outcome of evaluating and sending alerts."""

    enabled: bool
    evaluated: int
    matched: int
    sent: int
    skipped_cooldown: int
    skipped_unchanged: int = 0
    discord_ok: bool | None = None
    email_ok: bool | None = None
    events: list[AlertEvent] = field(default_factory=list)


def grade_meets_minimum(grade: str, minimum: str) -> bool:
    """Return True if trade grade is at least the configured minimum."""
    return _GRADE_RANK.get(grade.upper(), -1) >= _GRADE_RANK.get(minimum.upper(), 99)


def format_alert_text(event: AlertEvent) -> str:
    """Plain-text body for email / logs."""
    ref = event.trigger_ref or event.trigger
    lines = [
        f"Signal Engine alert: {event.symbol}",
        f"Ref: {ref}",
        f"Trigger: {event.trigger}",
        f"Confidence: {event.confidence:.1f}%",
        f"Grade: {event.trade_grade}",
        f"State: {event.trade_state} · Signal: {event.execution_signal}",
        f"Trend: {event.trend} · EV: {event.expected_value:.2f}",
        f"Class: {event.asset_class}",
    ]
    if event.prev_confidence is not None or event.prev_grade is not None:
        prev_c = f"{event.prev_confidence:.0f}%" if event.prev_confidence is not None else "—"
        prev_g = event.prev_grade or "—"
        lines.append(f"Prior: {prev_g} / {prev_c}")
    return "\n".join(lines)


def build_trigger_ref(
    *,
    trigger: str,
    confidence: float,
    trade_grade: str,
    trend: str,
    prev: AlertSnapshot | None,
) -> str:
    """Compact one-line ref for embeds (what changed / why we fired)."""
    now = f"{trade_grade} {confidence:.0f}% · {trend}"
    if prev is None or trigger == "threshold_cross":
        return f"{trigger} · {now}"
    return (
        f"{trigger} · {prev.trade_grade} {prev.confidence:.0f}%→"
        f"{trade_grade} {confidence:.0f}% · {trend}"
    )


class AlertService:
    """Evaluates asset summaries and dispatches Discord + email alerts."""

    def __init__(
        self,
        state_store: MemoryAlertStateStore | PostgresAlertStateStore | None = None,
    ) -> None:
        self._lock = Lock()
        self._state_store = state_store or build_alert_state_store()
        self._last_sent, self._last_alerted = self._state_store.load()
        self._backend = getattr(self._state_store, "backend", "memory")
        logger.info(
            "AlertService ready backend=%s symbols_loaded=%d",
            self._backend,
            len(self._last_sent),
        )

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
            # Bot preferred; webhook is fallback only (avoids duplicate channel posts)
            discord_mode = "bot+webhook_fallback"
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
            "email_configured": bool(settings.alert_email_to.strip() and smtp_configured()),
            "channels": {
                "discord": self.discord_configured(),
                "email": bool(settings.alert_email_to.strip() and smtp_configured()),
            },
            "state_backend": self._backend,
            "state_symbols": len(self._last_sent),
        }

    @staticmethod
    def _discord_embed(event: AlertEvent) -> dict:
        """Build a Discord embed payload for an alert event."""
        color = 0x8FA88A if event.confidence >= 70 else 0x9A958D
        ref = event.trigger_ref or event.trigger
        fields = [
            {"name": "Trend", "value": event.trend, "inline": True},
            {"name": "EV", "value": f"{event.expected_value:.2f}", "inline": True},
            {"name": "Class", "value": event.asset_class, "inline": True},
            {"name": "Ref", "value": ref, "inline": False},
        ]
        return {
            "title": f"{event.symbol} — grade {event.trade_grade}",
            "description": (
                f"**{event.confidence:.0f}%** confidence · "
                f"{event.trade_state} / {event.execution_signal}"
            ),
            "color": color,
            "fields": fields,
            "footer": {"text": f"Signal Engine · {event.trigger}"},
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def evaluate(self, assets: list[AssetSummary]) -> list[AlertEvent]:
        """Filter assets that meet confidence + grade thresholds (no trigger yet)."""
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

    def _classify_trigger(
        self, event: AlertEvent, prev: AlertSnapshot | None
    ) -> tuple[str, str] | None:
        """Return (trigger, ref) if we should fire, else None (unchanged hot).

        - No prior alert this process: threshold_cross
        - After cooldown, only re-fire on material change (grade↑, conf↑, trend flip)
        """
        if prev is None:
            trigger = "threshold_cross"
            ref = build_trigger_ref(
                trigger=trigger,
                confidence=event.confidence,
                trade_grade=event.trade_grade,
                trend=event.trend,
                prev=None,
            )
            return trigger, ref

        grade_up = _GRADE_RANK.get(event.trade_grade.upper(), -1) > _GRADE_RANK.get(
            prev.trade_grade.upper(), -1
        )
        conf_up = event.confidence >= prev.confidence + _MIN_CONFIDENCE_DELTA
        trend_flip = event.trend.strip().lower() != prev.trend.strip().lower()

        if grade_up:
            trigger = "grade_up"
        elif conf_up:
            trigger = "confidence_up"
        elif trend_flip:
            trigger = "trend_flip"
        else:
            return None

        ref = build_trigger_ref(
            trigger=trigger,
            confidence=event.confidence,
            trade_grade=event.trade_grade,
            trend=event.trend,
            prev=prev,
        )
        return trigger, ref

    def _mark_sent(self, event: AlertEvent) -> None:
        key = event.symbol.upper()
        now = datetime.now(UTC)
        snap = AlertSnapshot(
            confidence=event.confidence,
            trade_grade=event.trade_grade,
            trend=event.trend,
            trade_state=event.trade_state,
            execution_signal=event.execution_signal,
            expected_value=event.expected_value,
            at=now,
        )
        self._last_sent[key] = now
        self._last_alerted[key] = snap
        try:
            self._state_store.save_sent(key, now, snap)
        except Exception:
            logger.exception("Failed to persist alert state for %s", key)

    def _touch_cooldown(self, symbol: str) -> None:
        key = symbol.upper()
        now = datetime.now(UTC)
        self._last_sent[key] = now
        try:
            self._state_store.touch_cooldown(key, now)
        except Exception:
            logger.exception("Failed to persist alert cooldown for %s", key)

    def send_discord(self, event: AlertEvent) -> bool:
        """Post an embed via Discord bot, falling back to webhook if needed.

        When both are configured we send **once** (bot preferred) so the same
        channel is not spammed with duplicate messages.
        """
        embed = self._discord_embed(event)
        token = settings.alert_discord_bot_token.strip()
        channel_id = settings.alert_discord_channel_id.strip()
        webhook = settings.alert_discord_webhook_url.strip()

        if token and channel_id:
            if self._send_discord_bot(event.symbol, token, channel_id, embed):
                return True
            logger.warning("Discord bot failed for %s; trying webhook fallback", event.symbol)

        if webhook:
            return self._send_discord_webhook(event.symbol, webhook, embed)

        return False

    def send_embed(
        self,
        symbol: str,
        embed: dict,
        *,
        content: str | None = None,
        username: str = "Signal Engine",
    ) -> bool:
        """Post a custom embed (paper stamps, admin pings). Ignores alert_enabled."""
        if not self.discord_configured():
            return False
        token = settings.alert_discord_bot_token.strip()
        channel_id = settings.alert_discord_channel_id.strip()
        webhook = settings.alert_discord_webhook_url.strip()
        if token and channel_id:
            if self._send_discord_bot(symbol, token, channel_id, embed, content=content):
                return True
            logger.warning("Discord bot failed for %s; trying webhook fallback", symbol)
        if webhook:
            return self._send_discord_webhook(
                symbol, webhook, embed, content=content, username=username
            )
        return False

    def _send_discord_bot(
        self,
        symbol: str,
        token: str,
        channel_id: str,
        embed: dict,
        *,
        content: str | None = None,
    ) -> bool:
        """Send a channel message as our Discord application bot."""
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }
        payload: dict = {"embeds": [embed]}
        if content:
            payload["content"] = content
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            return True
        except Exception:
            logger.exception("Discord bot alert failed for %s", symbol)
            return False

    def _send_discord_webhook(
        self,
        symbol: str,
        url: str,
        embed: dict,
        *,
        content: str | None = None,
        username: str = "Signal Engine",
    ) -> bool:
        """Fallback: post embed to a Discord webhook URL."""
        payload: dict = {"username": username, "embeds": [embed]}
        if content:
            payload["content"] = content
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
        if not to_addr:
            return False
        return send_mail(
            to_addr,
            f"[Signal Engine] {event.symbol} {event.trade_grade} @ {event.confidence:.0f}%",
            format_alert_text(event),
        )

    def dispatch(self, assets: list[AssetSummary], *, force: bool = False) -> AlertDispatchResult:
        """Evaluate assets and send alerts for new crosses / material changes."""
        if not self.enabled and not force:
            return AlertDispatchResult(
                enabled=False,
                evaluated=len(assets),
                matched=0,
                sent=0,
                skipped_cooldown=0,
                skipped_unchanged=0,
                discord_ok=None,
                email_ok=None,
                events=[],
            )

        matches = self.evaluate(assets)
        sent = 0
        skipped = 0
        skipped_unchanged = 0
        fired: list[AlertEvent] = []
        discord_ok: bool | None = None
        email_ok: bool | None = None

        with self._lock:
            for event in matches:
                key = event.symbol.upper()
                if not force and self._cooldown_active(key):
                    skipped += 1
                    logger.debug(
                        "Alert skip cooldown %s conf=%.1f grade=%s",
                        key,
                        event.confidence,
                        event.trade_grade,
                    )
                    continue

                prev = self._last_alerted.get(key)
                classified = self._classify_trigger(event, prev)
                if classified is None and not force:
                    skipped_unchanged += 1
                    logger.info(
                        "Alert skip unchanged_hot %s conf=%.1f grade=%s trend=%s "
                        "(still above threshold, no material change vs last alert)",
                        key,
                        event.confidence,
                        event.trade_grade,
                        event.trend,
                    )
                    # Keep cooldown from re-checking every dashboard poll
                    self._touch_cooldown(key)
                    continue

                if classified is not None:
                    trigger, ref = classified
                else:
                    trigger, ref = "forced", build_trigger_ref(
                        trigger="forced",
                        confidence=event.confidence,
                        trade_grade=event.trade_grade,
                        trend=event.trend,
                        prev=prev,
                    )

                event.trigger = trigger
                event.trigger_ref = ref
                event.prev_confidence = prev.confidence if prev else None
                event.prev_grade = prev.trade_grade if prev else None

                logger.info(
                    "Alert fire %s trigger=%s ref=%r conf=%.1f grade=%s state=%s "
                    "signal=%s trend=%s ev=%.2f class=%s prev_conf=%s prev_grade=%s",
                    key,
                    event.trigger,
                    event.trigger_ref,
                    event.confidence,
                    event.trade_grade,
                    event.trade_state,
                    event.execution_signal,
                    event.trend,
                    event.expected_value,
                    event.asset_class,
                    event.prev_confidence,
                    event.prev_grade,
                )

                channel_hit = False
                if self.discord_configured():
                    d_ok = self.send_discord(event)
                    discord_ok = (discord_ok is True) or d_ok
                    channel_hit = channel_hit or d_ok
                if settings.alert_email_to.strip() and smtp_configured():
                    e_ok = self.send_email(event)
                    email_ok = (email_ok is True) or e_ok
                    channel_hit = channel_hit or e_ok

                if channel_hit:
                    self._mark_sent(event)
                    sent += 1
                    fired.append(event)
                elif not (
                    self.discord_configured()
                    or (settings.alert_email_to.strip() and smtp_configured())
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
            skipped_unchanged=skipped_unchanged,
            discord_ok=discord_ok,
            email_ok=email_ok,
            events=fired,
        )

    def send_paper_test(self) -> dict[str, bool | str]:
        """Mint a paper-desk stamp and post it to Discord (new paper path)."""
        from datetime import UTC, datetime

        from app.engines.paper_agent.stamps import mint_stamp, paper_discord_payload
        from app.engines.paper_agent.types import PaperTrade

        now = datetime.now(UTC)
        trade = PaperTrade(
            id="paper-test",
            symbol="BTC",
            source="crypto_setup",
            setup_type="funding_extreme",
            direction="short",
            fingerprint="paper-test",
            signal_at=now,
            confidence=72.0,
            opportunity_score=72.0,
            size_usd=2500.0,
            status="open",
            optimistic_entry=65000.0,
            optimistic_entry_at=now,
            take_profit_pct=8.0,
            stop_loss_pct=4.0,
        )
        stamp = mint_stamp(trade.id)
        trade.stamp = stamp.line
        content, embed = paper_discord_payload("open", trade, stamp)
        content = content.replace("PAPER OPEN", "PAPER OPEN (TEST)", 1)
        embed["footer"]["text"] = f"{stamp.office} · {stamp.serial} · paper desk TEST"
        ok = (
            self.send_embed(
                trade.symbol,
                embed,
                content=content,
                username="Paper Desk",
            )
            if self.discord_configured()
            else False
        )
        return {
            "symbol": "BTC",
            "discord": ok,
            "discord_mode": self.status()["discord_mode"],
            "stamp": stamp.line,
            "configured": self.discord_configured(),
        }

    def send_test(self, channel: str = "both") -> dict[str, bool | str]:
        """Send a test alert to configured channels."""
        if channel == "paper":
            return self.send_paper_test()
        event = AlertEvent(
            symbol="TEST",
            confidence=72.0,
            trade_grade="B",
            trade_state="WATCH",
            execution_signal="WATCH",
            expected_value=0.42,
            trend="Bullish",
            asset_class="etf",
            trigger="test",
            trigger_ref="test · B 72% · Bullish",
        )
        result: dict[str, bool | str] = {"symbol": "TEST"}
        if channel in {"both", "discord"}:
            result["discord"] = self.send_discord(event) if self.discord_configured() else False
            result["discord_mode"] = self.status()["discord_mode"]
        if channel in {"both", "email"}:
            result["email"] = (
                self.send_email(event)
                if (settings.alert_email_to.strip() and smtp_configured())
                else False
            )
        return result
