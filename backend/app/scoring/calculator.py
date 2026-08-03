"""Confidence score calculation from evidence items."""

from app.engines.evidence_engine.types import EvidenceItem
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, validate_weights


def calculate_total_confidence(
    items: list[EvidenceItem],
    weights: dict[ScoringCategory, float] | None = None,
    regime_multiplier: dict[ScoringCategory, float] | None = None,
) -> float:
    """Compute weighted total confidence from evidence items.

    Each item's contribution is ``(score / 100) * effective_weight``.
    Effective weight applies optional regime multipliers per category.

    Args:
        items: Evidence items from analysis engines.
        weights: Category weights; defaults to ``DEFAULT_WEIGHTS``.
        regime_multiplier: Optional per-category multipliers from Regime Engine.

    Returns:
        Total confidence score clamped to 0–100.
    """
    active_weights = weights or DEFAULT_WEIGHTS
    validate_weights(active_weights)
    multipliers = regime_multiplier or {}

    total = 0.0
    for item in items:
        category = ScoringCategory(item.category)
        base_weight = active_weights.get(category, item.weight)
        effective_weight = base_weight * multipliers.get(category, 1.0)
        total += (item.score / 100.0) * effective_weight

    return round(min(max(total, 0.0), 100.0), 2)
