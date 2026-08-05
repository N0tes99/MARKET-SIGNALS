"""Scoring module tests."""

import pytest

from app.engines.evidence_engine.types import EvidenceItem
from app.scoring.calculator import calculate_total_confidence
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, validate_weights


def test_default_weights_sum_to_100() -> None:
    """Default category weights must sum to exactly 100."""
    assert sum(DEFAULT_WEIGHTS.values()) == 100.0


def test_validate_weights_rejects_invalid_total() -> None:
    """Weight validation rejects configs that do not sum to 100."""
    bad_weights = {ScoringCategory.TREND: 50.0, ScoringCategory.MACRO: 10.0}
    with pytest.raises(ValueError, match="must sum to 100"):
        validate_weights(bad_weights)


def test_calculate_total_confidence_perfect_scores() -> None:
    """All categories at 100 should produce total confidence of 100."""
    items = [
        EvidenceItem(
            source="test",
            category=category.value,
            score=100.0,
            weight=weight,
            description="test",
        )
        for category, weight in DEFAULT_WEIGHTS.items()
    ]
    assert calculate_total_confidence(items) == 100.0


def test_calculate_total_confidence_zero_scores() -> None:
    """All categories at 0 should produce total confidence of 0."""
    items = [
        EvidenceItem(
            source="test",
            category=category.value,
            score=0.0,
            weight=weight,
            description="test",
        )
        for category, weight in DEFAULT_WEIGHTS.items()
    ]
    assert calculate_total_confidence(items) == 0.0


def test_calculate_total_confidence_partial() -> None:
    """Weighted calculation should reflect partial scores."""
    trend_w = DEFAULT_WEIGHTS[ScoringCategory.TREND]
    mom_w = DEFAULT_WEIGHTS[ScoringCategory.MOMENTUM]
    items = [
        EvidenceItem(
            source="trend_engine",
            category="Trend",
            score=80.0,
            weight=trend_w,
            description="Strong uptrend",
        ),
        EvidenceItem(
            source="buyer_seller_engine",
            category="Momentum",
            score=60.0,
            weight=mom_w,
            description="Moderate momentum",
        ),
    ]
    expected = round((80 / 100 * trend_w) + (60 / 100 * mom_w), 2)
    assert calculate_total_confidence(items) == expected
