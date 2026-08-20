"""Discord alerts when expansion radar escalates (PRIMED / TRIGGER / EXPANSION)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock

from app.cortex.types import AlertLevel, WorkingMemory

logger = logging.getLogger(__name__)

_ALERT_RANK: dict[AlertLevel, int] = {
    "none": 0,
    "watch": 1,
    "primed": 2,
    "trigger": 3,
    "expansion": 4,
}

_NOTIFY_LEVELS = frozenset({"primed", "trigger", "expansion"})


class ExpansionAlertService:
    """Fire Discord when alert level escalates for a benchmark symbol."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_level: dict[str, AlertLevel] = {}
        self._last_sent: dict[str, datetime] = {}

    def notify_memory(self, memory: WorkingMemory, alerts) -> list[str]:
        """Compare to prior levels; send embeds on escalation. Returns note lines."""
        if alerts is None:
            return []
        notes: list[str] = []
        now = datetime.now(UTC)
        for sym, ctx in memory.symbols.items():
            level = ctx.alert_level
            if level not in _NOTIFY_LEVELS:
                continue
            key = sym.upper()
            with self._lock:
                prior = self._last_level.get(key, "none")
            if _ALERT_RANK[level] <= _ALERT_RANK[prior]:
                continue
            sent = self._send(sym, level, ctx, memory.tick_id, alerts)
            with self._lock:
                self._last_level[key] = level
                if sent:
                    self._last_sent[key] = now
            tag = f"alert:{sym}:{level}"
            notes.append(tag)
            logger.info("Expansion alert %s level=%s sent=%s", sym, level, sent)
        return notes

    def _send(self, symbol: str, level: AlertLevel, ctx, tick_id: str, alerts) -> bool:
        exp = ctx.expansion
        if exp is None:
            return False
        color = {"primed": 0xF59E0B, "trigger": 0xF97316, "expansion": 0x22C55E}.get(level, 0x6366F1)
        title = {
            "primed": f"{symbol} — PRIMED (compression setup)",
            "trigger": f"{symbol} — TRIGGER (breakout firing)",
            "expansion": f"{symbol} — EXPANDING",
        }.get(level, f"{symbol} expansion")
        fields = [
            {"name": "State", "value": exp.state.value, "inline": True},
            {"name": "Net score", "value": f"{exp.net_score:.0f}", "inline": True},
            {"name": "Bias", "value": exp.direction_bias, "inline": True},
            {
                "name": "Compression",
                "value": f"{exp.compression.score:.0f}",
                "inline": True,
            },
            {"name": "Squeeze", "value": f"{exp.squeeze.score:.0f}", "inline": True},
            {
                "name": "Trigger",
                "value": "active" if exp.trigger_active else "idle",
                "inline": True,
            },
        ]
        if ctx.synthesis_notes:
            fields.append(
                {
                    "name": "Synthesis",
                    "value": "; ".join(ctx.synthesis_notes[:2])[:256],
                    "inline": False,
                }
            )
        embed = {
            "title": title,
            "description": exp.key_trigger[:200] if exp.key_trigger else "Expansion radar escalation",
            "color": color,
            "fields": fields,
            "footer": {"text": f"cortex {tick_id} · paper opens on trigger/expansion only"},
        }
        try:
            return bool(alerts.send_embed(symbol, embed, content=f"**Expansion radar · {level.upper()}**"))
        except Exception:
            logger.exception("Expansion Discord alert failed for %s", symbol)
            return False


_expansion_alerts: ExpansionAlertService | None = None


def get_expansion_alert_service() -> ExpansionAlertService:
    global _expansion_alerts
    if _expansion_alerts is None:
        _expansion_alerts = ExpansionAlertService()
    return _expansion_alerts
