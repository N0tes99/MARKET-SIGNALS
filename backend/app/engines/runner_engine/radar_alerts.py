"""Discord pings when Radar watchlists jump — baseline scan is silent."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.config import settings
from app.engines.runner_engine.types import RunnerCandidate

logger = logging.getLogger(__name__)

_lock = Lock()
_prev: dict[str, tuple[str, str, str]] = {}
_last_sent: dict[str, datetime] = {}

_GATE_COLORS = {
    "early": 0x6B8E9F,
    "high": 0xC9A227,
    "ignition": 0xC9A227,
    "running": 0x8FA88A,
    "runner_failure": 0xA67C7C,
}


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


def _embed(key: str, reason: str, prev_watch: str, watch: str, cand: RunnerCandidate) -> dict:
    if reason in {"early", "high"}:
        description = (
            f"gate {reason} · {watch} · runner {cand.scores.runner_score:.0f} · "
            f"stage {cand.stage.replace('_', ' ')}"
        )
        title = f"Radar {reason} · {key}"
    else:
        description = (
            f"{prev_watch} → {watch} · runner {cand.scores.runner_score:.0f} · "
            f"stage {cand.stage.replace('_', ' ')}"
        )
        title = f"Radar {reason} · {key}"
    return {
        "title": title,
        "description": description,
        "color": _GATE_COLORS.get(reason, 0x8FA88A),
    }


def note_scan(candidates: list[RunnerCandidate], alerts=None) -> list[str]:
    """Record watchlists; ping Discord on upgrades / gate changes after first sighting."""
    fired: list[str] = []
    cooldown = timedelta(minutes=max(1, int(settings.alert_cooldown_minutes)))
    now = datetime.now(UTC)
    for cand in candidates:
        key = cand.symbol.upper()
        watch = cand.watchlist
        signal = cand.signal_type
        gate = cand.alert_gate if cand.alert_gate in {"early", "high"} else "none"
        with _lock:
            prev = _prev.get(key)
            _prev[key] = (watch, signal, gate)
            if prev is None:
                continue
            prev_watch, prev_signal = prev[0], prev[1]
            prev_gate = prev[2] if len(prev) > 2 else "none"
            reasons: list[str] = []
            list_reason = _should_fire(prev_watch, prev_signal, watch, signal)
            if list_reason is not None:
                reasons.append(list_reason)
            if gate in {"early", "high"} and prev_gate != gate:
                reasons.append(gate)
            pending: list[str] = []
            for reason in reasons:
                cool_key = f"{key}:{reason}"
                last = _last_sent.get(cool_key)
                if last is not None and now - last < cooldown:
                    continue
                _last_sent[cool_key] = now
                pending.append(reason)
        for reason in pending:
            fired.append(f"{key}:{reason}")
            logger.info(
                "radar_transition %s %s→%s signal=%s gate=%s reason=%s",
                key,
                prev_watch,
                watch,
                signal,
                gate,
                reason,
            )
            if alerts is None or not settings.alert_enabled:
                continue
            try:
                alerts.send_embed(
                    key,
                    _embed(key, reason, prev_watch, watch, cand),
                    username="Radar",
                )
            except Exception:
                logger.exception("Radar Discord failed for %s", key)
    return fired
