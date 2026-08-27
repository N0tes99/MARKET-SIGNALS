"""Compose directional expansion scores from named, normalized weights."""

from __future__ import annotations

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.scoring.weights import ExpansionWeights, weights_from_config
from app.engines.expansion_engine.types import (
    CompressionResult,
    ExpansionState,
    ScoreContributor,
    SqueezeFuelResult,
    TriggerResult,
)
from app.utils.scoring_helpers import clamp_score


def compose_scores(
    *,
    compression: CompressionResult | None,
    squeeze: SqueezeFuelResult,
    trigger: TriggerResult,
    mom_12h_pct: float | None,
    funding_bps: float | None,
    state: ExpansionState,
    config: ExpansionConfig | None = None,
    weights: ExpansionWeights | None = None,
) -> tuple[float, float, list[ScoreContributor], list[str]]:
    """Return (up_score, down_score, contributors, conflicts).

    Weights come from live procedural policy (normalized). Pass ``weights``
    in tests to pin a vector without hitting the config store.
    """
    cfg = config or default_expansion_config()
    w = (weights or weights_from_config(cfg)).normalize()
    contributors: list[ScoreContributor] = []
    conflicts: list[str] = list(squeeze.conflicts)

    contributors.append(
        ScoreContributor(
            "Policy",
            0.0,
            f"{w.source} v{w.version} · w={w.compression:.2f}/{w.squeeze:.2f}/"
            f"{w.trigger:.2f}/{w.momentum:.2f}/{w.derivatives:.2f}",
        )
    )

    comp_score = compression.score if compression else 50.0
    contributors.append(ScoreContributor("Compression", comp_score * w.compression, ""))

    up = comp_score * w.compression
    down = comp_score * w.compression

    sq = squeeze.score
    if squeeze.direction == "up":
        up += sq * w.squeeze
        contributors.append(ScoreContributor("Squeeze fuel", sq * w.squeeze, "upside"))
    elif squeeze.direction == "down":
        down += sq * w.squeeze
        contributors.append(ScoreContributor("Squeeze fuel", sq * w.squeeze, "downside"))
    else:
        up += sq * w.squeeze * 0.5
        down += sq * w.squeeze * 0.5

    if trigger.active:
        trig_pts = 80.0 * w.trigger
        if trigger.direction == "up":
            up += trig_pts
            contributors.append(ScoreContributor("Trigger", trig_pts, "breakout up"))
        elif trigger.direction == "down":
            down += trig_pts
            contributors.append(ScoreContributor("Trigger", trig_pts, "breakout down"))
    else:
        conflicts.append("No active breakout trigger")

    if mom_12h_pct is not None:
        mom_pts = min(abs(mom_12h_pct), 12.0) * w.momentum * 3.0
        if mom_12h_pct > 0:
            up += mom_pts
            contributors.append(ScoreContributor("Momentum 12h", mom_pts, f"{mom_12h_pct:+.1f}%"))
        elif mom_12h_pct < 0:
            down += mom_pts
            contributors.append(ScoreContributor("Momentum 12h", mom_pts, f"{mom_12h_pct:+.1f}%"))

    if funding_bps is not None:
        deriv_pts = w.derivatives * 50.0
        if funding_bps >= cfg.squeeze_funding_soft_bps:
            up += deriv_pts * 0.6
            contributors.append(
                ScoreContributor("Derivatives", deriv_pts * 0.6, "funding supports up")
            )
        elif funding_bps <= -cfg.squeeze_funding_soft_bps:
            down += deriv_pts * 0.6
            contributors.append(
                ScoreContributor("Derivatives", deriv_pts * 0.6, "funding supports down")
            )

    if state == ExpansionState.PRIMED:
        up = clamp_score(up + 5.0)
        down = clamp_score(down + 5.0)
    elif state == ExpansionState.TRIGGERING:
        up = clamp_score(up + 10.0)
        down = clamp_score(down + 10.0)
    elif state == ExpansionState.EXPANDING:
        up = clamp_score(up + 15.0)
        down = clamp_score(down + 15.0)

    return clamp_score(up), clamp_score(down), contributors, conflicts
