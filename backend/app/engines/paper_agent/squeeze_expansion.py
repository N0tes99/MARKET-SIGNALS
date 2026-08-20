"""Paper feed: cortex TRIGGER/EXPANSION → squeeze_expansion ideas.

Separate from perp_momentum. PRIMED is WATCH-only — never opens paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.cortex.synthesis import alert_level_for
from app.cortex.types import WorkingMemory
from app.engines.expansion_engine.types import ExpansionCandidate
from app.engines.paper_agent.types import PaperDirection

SETUP_TYPE = "squeeze_expansion"
SOURCE = "squeeze_expansion"
MAX_OPENS_PER_DAY = 1
TRADEABLE_ALERTS = frozenset({"trigger", "expansion"})
MIN_NET_SCORE = 80.0


class _CortexLike(Protocol):
    last_memory: WorkingMemory | None

    def tick(self, *, persist: bool = True) -> WorkingMemory: ...


@dataclass(frozen=True)
class SqueezeExpansionIdea:
    """One paper-eligible expansion trigger."""

    symbol: str
    direction: PaperDirection
    setup_type: str
    confidence: float
    factors: list[str]
    extras: dict[str, Any] = field(default_factory=dict)


def _direction(bias: str) -> PaperDirection | None:
    if bias == "up":
        return "long"
    if bias == "down":
        return "short"
    return None


def is_tradeable(candidate: ExpansionCandidate) -> bool:
    """True when cortex would allow a paper open (TRIGGER/EXPANSION only)."""
    if alert_level_for(candidate) not in TRADEABLE_ALERTS:
        return False
    if candidate.net_score < MIN_NET_SCORE:
        return False
    return _direction(candidate.direction_bias) is not None


def idea_from_candidate(
    candidate: ExpansionCandidate,
    *,
    tick_id: str | None = None,
    alert_level: str | None = None,
) -> SqueezeExpansionIdea | None:
    if not is_tradeable(candidate):
        return None
    direction = _direction(candidate.direction_bias)
    if direction is None:
        return None
    level = alert_level or alert_level_for(candidate)
    factors = [
        f"Cortex {level}",
        f"State {candidate.state.value}",
        *list(candidate.factors[:3]),
    ]
    extras: dict[str, Any] = {
        "tick_id": tick_id,
        "expansion_state": candidate.state.value,
        "alert_level": level,
        "compression_score": candidate.compression.score,
        "squeeze_score": candidate.squeeze.score,
        "trigger_active": candidate.trigger_active,
        "up_score": candidate.up_score,
        "down_score": candidate.down_score,
        "funding_bps": candidate.funding_bps,
        "mom_12h_pct": candidate.mom_12h_pct,
    }
    return SqueezeExpansionIdea(
        symbol=candidate.symbol,
        direction=direction,
        setup_type=SETUP_TYPE,
        confidence=float(candidate.net_score),
        factors=factors,
        extras=extras,
    )


def ideas_from_working_memory(memory: WorkingMemory) -> list[SqueezeExpansionIdea]:
    """Convert a cortex blackboard into paper ideas."""
    ideas: list[SqueezeExpansionIdea] = []
    for ctx in memory.symbols.values():
        if ctx.expansion is None:
            continue
        if ctx.alert_level not in TRADEABLE_ALERTS:
            continue
        idea = idea_from_candidate(
            ctx.expansion,
            tick_id=memory.tick_id,
            alert_level=ctx.alert_level,
        )
        if idea is not None:
            ideas.append(idea)
    ideas.sort(key=lambda i: i.confidence, reverse=True)
    return ideas


def scan_squeeze_expansion(cortex: _CortexLike) -> list[SqueezeExpansionIdea]:
    """Use last cortex memory, or run one tick if empty."""
    memory = cortex.last_memory
    if memory is None:
        memory = cortex.tick(persist=True)
    return ideas_from_working_memory(memory)
