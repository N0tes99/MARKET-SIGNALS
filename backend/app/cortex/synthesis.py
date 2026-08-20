"""Synthesis helpers — merge specialist opinions into notes and alerts."""

from __future__ import annotations

from app.cortex.types import AlertLevel, SpecialistOpinion, SymbolContext
from app.engines.expansion_engine.config import default_expansion_config
from app.engines.expansion_engine.types import ExpansionCandidate, ExpansionState


def alert_level_for(expansion: ExpansionCandidate | None) -> AlertLevel:
    if expansion is None:
        return "none"
    cfg = default_expansion_config()
    net = expansion.net_score
    state = expansion.state

    if state == ExpansionState.EXPANDING and net >= cfg.trigger_net_score:
        return "expansion"
    if state == ExpansionState.TRIGGERING and net >= cfg.trigger_net_score:
        return "trigger"
    if state == ExpansionState.PRIMED and net >= cfg.primed_net_score:
        return "primed"
    if net >= cfg.watch_net_score:
        return "watch"
    return "none"


def synthesize_symbol_notes(ctx: SymbolContext) -> list[str]:
    """Cross-specialist synthesis — regime confirms compression, etc."""
    notes: list[str] = []
    expansion = ctx.expansion
    if expansion is None:
        return notes

    regime = _find_opinion(ctx.opinions, "regime")
    if (
        expansion.compression.score >= 75
        and regime is not None
        and regime.metadata.get("regime") == "Quiet"
    ):
        notes.append("Regime QUIET confirms compression setup")

    deriv = _find_opinion(ctx.opinions, "derivatives")
    if (
        expansion.squeeze.score >= 65
        and deriv is not None
        and (deriv.score or 0) >= 55
    ):
        notes.append("Derivatives positioning supports squeeze fuel")

    if expansion.trigger_active:
        notes.append(f"Trigger active — {expansion.key_trigger}")

    return notes


def expansion_to_opinion(candidate: ExpansionCandidate) -> SpecialistOpinion:
    return SpecialistOpinion(
        specialist="expansion",
        score=candidate.net_score,
        direction=candidate.direction_bias,
        factors=list(candidate.factors[:6]),
        conflicts=list(candidate.conflicts[:4]),
        metadata={
            "state": candidate.state.value,
            "up_score": candidate.up_score,
            "down_score": candidate.down_score,
            "trigger_active": candidate.trigger_active,
            "compression_score": candidate.compression.score,
            "squeeze_score": candidate.squeeze.score,
        },
    )


def _find_opinion(opinions: list[SpecialistOpinion], name: str) -> SpecialistOpinion | None:
    for op in opinions:
        if op.specialist == name:
            return op
    return None
