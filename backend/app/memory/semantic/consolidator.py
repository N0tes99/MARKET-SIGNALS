"""Consolidate episodic cortex ticks into lead-time and calibration stats."""

from __future__ import annotations

import logging
import statistics
from datetime import UTC, datetime

from app.memory.episodic.store import EpisodicStore
from app.memory.episodic.types import EpisodicRecord
from app.memory.semantic.store import SemanticStore
from app.memory.semantic.types import SemanticStat

logger = logging.getLogger(__name__)

LEAD_SIGNAL = "primed_to_trigger"
HIT_HORIZON_HOURS = 12.0


def _parse_as_of(value: object, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return fallback
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _symbol_state(payload: dict, symbol: str) -> tuple[str | None, float | None]:
    symbols = payload.get("symbols") or {}
    ctx = symbols.get(symbol) or {}
    expansion = ctx.get("expansion") or {}
    state = expansion.get("state") or ctx.get("alert_level")
    net = expansion.get("net_score")
    try:
        net_f = float(net) if net is not None else None
    except (TypeError, ValueError):
        net_f = None
    return (str(state) if state else None, net_f)


def _score_bucket(net: float | None) -> int:
    if net is None:
        return -1
    return int(net // 10) * 10


def consolidate_from_episodic(
    episodic: EpisodicStore,
    semantic: SemanticStore,
    *,
    history_limit: int = 200,
) -> list[SemanticStat]:
    """Walk episodic history and write lead-time + calibration stats.

    Lead time: hours from first PRIMED to first TRIGGERING/EXPANDING per symbol.
    Calibration: primed score bucket hit-rate if a trigger follows within 12h.
    """
    records = episodic.history(limit=history_limit)
    if len(records) < 2:
        return []

    stats = _compute_stats(records)
    for stat in stats:
        try:
            semantic.upsert(stat)
        except Exception:
            logger.exception("Semantic upsert failed for %s/%s", stat.metric, stat.signal)
    return stats


def _compute_stats(records: list[EpisodicRecord]) -> list[SemanticStat]:
    symbols: set[str] = set()
    for rec in records:
        symbols.update((rec.payload.get("symbols") or {}).keys())

    lead_hours: list[float] = []
    # bucket -> [hits]
    cal_hits: dict[int, list[bool]] = {}

    now = records[-1].as_of

    for symbol in symbols:
        primed_at: datetime | None = None
        primed_score: float | None = None
        resolved = False
        for rec in records:
            state, net = _symbol_state(rec.payload, symbol)
            as_of = _parse_as_of(rec.payload.get("as_of"), rec.as_of)
            if state == "primed" and primed_at is None:
                primed_at = as_of
                primed_score = net
                resolved = False
                continue
            if primed_at is None:
                continue
            if state in {"triggering", "expanding", "trigger", "expansion"}:
                hours = (as_of - primed_at).total_seconds() / 3600.0
                if hours >= 0:
                    lead_hours.append(hours)
                    bucket = _score_bucket(primed_score)
                    cal_hits.setdefault(bucket, []).append(hours <= HIT_HORIZON_HOURS)
                primed_at = None
                primed_score = None
                resolved = True
                continue
            if state == "dormant" and not resolved:
                bucket = _score_bucket(primed_score)
                cal_hits.setdefault(bucket, []).append(False)
                primed_at = None
                primed_score = None
                resolved = True

        if primed_at is not None and not resolved:
            open_hours = (now - primed_at).total_seconds() / 3600.0
            if open_hours > HIT_HORIZON_HOURS:
                bucket = _score_bucket(primed_score)
                cal_hits.setdefault(bucket, []).append(False)

    stats: list[SemanticStat] = []
    if lead_hours:
        stats.append(
            SemanticStat(
                metric="lead_time",
                signal=LEAD_SIGNAL,
                sample_count=len(lead_hours),
                median_hours=round(float(statistics.median(lead_hours)), 3),
                payload={"hours": [round(h, 3) for h in lead_hours[-50:]]},
            )
        )

    for bucket, outcomes in sorted(cal_hits.items()):
        if not outcomes:
            continue
        hits = sum(1 for x in outcomes if x)
        stats.append(
            SemanticStat(
                metric="calibration",
                signal=LEAD_SIGNAL,
                score_bucket=bucket,
                sample_count=len(outcomes),
                hit_rate=round(hits / len(outcomes), 4),
                payload={"hits": hits, "misses": len(outcomes) - hits},
            )
        )
    return stats
