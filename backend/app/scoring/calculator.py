"""Confidence score calculation from evidence items."""

from typing import Protocol

from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, validate_weights

_CONF_MIN = 0.5
_CONF_MAX = 1.5


class _ScoredEvidence(Protocol):
    """Minimal evidence shape needed for confidence aggregation."""

    category: str
    score: float
    weight: float


def _clamp_item_confidence(confidence: float) -> float:
    """Clamp per-item confidence to the allowed scoring band."""
    return min(max(confidence, _CONF_MIN), _CONF_MAX)


def calculate_total_confidence(
    items: list[_ScoredEvidence],
    weights: dict[ScoringCategory, float] | None = None,
) -> float:
    """Compute weighted total confidence from evidence items.

    Each item's contribution is::

        weight × (score / 100) × clamp(confidence, 0.5, 1.5)

    The final total is clamped to 0–100. Weights are **not** renormalized
    when item confidence differs from 1.0.

    Args:
        items: Evidence items from analysis engines.
        weights: Category weights; defaults to ``DEFAULT_WEIGHTS``.

    Returns:
        Total confidence score clamped to 0–100.
    """
    active_weights = weights or DEFAULT_WEIGHTS
    validate_weights(active_weights)

    total = 0.0
    for item in items:
        category = ScoringCategory(item.category)
        base_weight = active_weights.get(category, item.weight)
        conf = _clamp_item_confidence(getattr(item, "confidence", 1.0))
        total += base_weight * (item.score / 100.0) * conf

    return round(min(max(total, 0.0), 100.0), 2)
