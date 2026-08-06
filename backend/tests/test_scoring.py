"""Scoring module tests."""

import pytest

from app.engines.evidence_engine.types import EvidenceItem
from app.scoring.calculator import calculate_total_confidence
from app.scoring.weights import (
    DEFAULT_WEIGHTS,
    REGIME_WEIGHT_PROFILES,
    ScoringCategory,
    WeightProfile,
    resolve_weight_profile,
    validate_weights,
)


def test_default_weights_sum_to_100() -> None:
    """Default category weights must sum to exactly 100."""
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 100.0) < 0.01


def test_default_weights_core_and_residual_bands() -> None:
    """Core seven ~80–85; residual extras ~15–20 of total."""
    core = (
        ScoringCategory.STRUCTURE,
        ScoringCategory.MOMENTUM,
        ScoringCategory.TREND,
        ScoringCategory.RISK,
        ScoringCategory.VOLUME,
        ScoringCategory.MACRO,
        ScoringCategory.DERIVATIVES,
    )
    core_sum = sum(DEFAULT_WEIGHTS[c] for c in core)
    residual = 100.0 - core_sum
    assert 80.0 <= core_sum <= 85.0
    assert 15.0 <= residual <= 20.0
    assert DEFAULT_WEIGHTS[ScoringCategory.STRUCTURE] > DEFAULT_WEIGHTS[ScoringCategory.TREND]
    assert DEFAULT_WEIGHTS[ScoringCategory.MOMENTUM] > DEFAULT_WEIGHTS[ScoringCategory.VOLUME]


def test_regime_profiles_sum_to_100() -> None:
    """Each regime weight profile sums to 100 and covers all categories."""
    for profile, weights in REGIME_WEIGHT_PROFILES.items():
        validate_weights(weights)
        assert set(weights) == set(ScoringCategory)
        assert profile in WeightProfile


def test_resolve_weight_profile_mapping() -> None:
    """Regime labels (+ VIX) map to the locked scoring profiles."""
    assert resolve_weight_profile("Trending") == WeightProfile.TRENDING
    assert resolve_weight_profile("Ranging") == WeightProfile.CHOPPY
    assert resolve_weight_profile("Quiet") == WeightProfile.CHOPPY
    assert resolve_weight_profile("Volatile") == WeightProfile.HIGH_VOL
    assert resolve_weight_profile("Trending", vix=30.0) == WeightProfile.HIGH_VOL
    assert resolve_weight_profile("Ranging", vix=30.0) == WeightProfile.HIGH_VOL
    assert resolve_weight_profile("Trending", vix=20.0) == WeightProfile.TRENDING


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


def _two_item_bundle(conf_a: float = 1.0, conf_b: float = 1.0) -> list[EvidenceItem]:
    trend_w = DEFAULT_WEIGHTS[ScoringCategory.TREND]
    mom_w = DEFAULT_WEIGHTS[ScoringCategory.MOMENTUM]
    return [
        EvidenceItem("t", "Trend", 80.0, trend_w, "t", confidence=conf_a),
        EvidenceItem("m", "Momentum", 60.0, mom_w, "m", confidence=conf_b),
    ]


def test_item_confidence_default_matches_baseline() -> None:
    """confidence=1.0 matches the no-confidence baseline contribution."""
    baseline = calculate_total_confidence(_two_item_bundle())
    assert calculate_total_confidence(_two_item_bundle(1.0, 1.0)) == baseline


def test_item_confidence_boost_at_1_5() -> None:
    """confidence=1.5 increases contribution vs baseline."""
    baseline = calculate_total_confidence(_two_item_bundle())
    boosted = calculate_total_confidence(_two_item_bundle(1.5, 1.5))
    assert boosted > baseline


def test_item_confidence_dampen_at_0_5() -> None:
    """confidence=0.5 decreases contribution vs baseline."""
    baseline = calculate_total_confidence(_two_item_bundle())
    dampened = calculate_total_confidence(_two_item_bundle(0.5, 0.5))
    assert dampened < baseline


def test_item_confidence_clamped_at_ends() -> None:
    """Values outside 0.5–1.5 are clamped; no weight renormalization."""
    trend_w = DEFAULT_WEIGHTS[ScoringCategory.TREND]
    item_low = [EvidenceItem("t", "Trend", 100.0, trend_w, "t", confidence=0.1)]
    item_high = [EvidenceItem("t", "Trend", 100.0, trend_w, "t", confidence=2.0)]
    assert calculate_total_confidence(item_low) == round(trend_w * 0.5, 2)
    assert calculate_total_confidence(item_high) == round(trend_w * 1.5, 2)
    # Perfect scores with 1.5 conf can exceed 100 before clamp
    all_boosted = [
        EvidenceItem("x", cat.value, 100.0, w, "x", confidence=1.5)
        for cat, w in DEFAULT_WEIGHTS.items()
    ]
    assert calculate_total_confidence(all_boosted) == 100.0
