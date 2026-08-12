"""Discord pings when Radar watchlists jump — baseline scan is silent."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.config import settings
from app.engines.runner_engine.types import RunnerCandidate

logger = logging.getLogger(__name__)

_lock = Lock()
_prev: dict[str, tuple[str, str]] = {}
_last_sent: dict[str, datetime] = {}


def reset_radar_alert_state() -> None:
    """Tests — forget prior lists."""
    with _lock:
        _prev.clear()
        _last_sent.clear()


def _should_fire(prev_watch: str, prev_signal: str, watch: str, signal: str) -> str | None:
    if (
        signal == "runner_failure"
        and prev_signal != "runner_failure"
        and (prev_watch in {"ignition", "running"} or watch in {"ignition", "running"})
    ):
        return "runner_failure"
    if watch == "ignition" and prev_watch == "early" and signal != "runner_failure":
        return "ignition"
    if watch == "running" and prev_watch != "running" and signal != "runner_failure":
        return "running"
    return None


def note_scan(candidates: list[RunnerCandidate], alerts=None) -> list[str]:
    """Record watchlists; ping Discord on upgrades after the first sighting."""
    fired: list[str] = []
    cooldown = timedelta(minutes=max(1, int(settings.alert_cooldown_minutes)))
    now = datetime.now(UTC)
    for cand in candidates:
        key = cand.symbol.upper()
        watch = cand.watchlist
        signal = cand.signal_type
        with _lock:
            prev = _prev.get(key)
            _prev[key] = (watch, signal)
            if prev is None:
                continue
            reason = _should_fire(prev[0], prev[1], watch, signal)
            if reason is None:
                continue
            cool_key = f"{key}:{reason}"
            last = _last_sent.get(cool_key)
            if last is not None and now - last < cooldown:
                continue
            _last_sent[cool_key] = now
        fired.append(f"{key}:{reason}")
        logger.info(
            "radar_transition %s %s→%s signal=%s reason=%s",
            key,
            prev[0],
            watch,
            signal,
            reason,
        )
        if alerts is None or not settings.alert_enabled:
            continue
        embed = {
            "title": f"Radar {reason} · {key}",
            "description": (
                f"{prev[0]} → {watch} · runner {cand.scores.runner_score:.0f} · "
                f"stage {cand.stage.replace('_', ' ')}"
            ),
            "color": 0xC9A227 if reason == "ignition" else 0x8FA88A,
        }
        if reason == "runner_failure":
            embed["color"] = 0xA67C7C
        try:
            alerts.send_embed(key, embed, username="Radar")
        except Exception:
            logger.exception("Radar Discord failed for %s", key)
    return fired
