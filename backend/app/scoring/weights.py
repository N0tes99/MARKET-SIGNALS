"""Default scoring category weights and regime weight profiles."""

from enum import StrEnum


class ScoringCategory(StrEnum):
    """Evidence categories that combine into total confidence."""

    TREND = "Trend"
    MOMENTUM = "Momentum"
    VOLUME = "Volume"
    STRUCTURE = "Structure"
    RISK = "Risk"
    MACRO = "Macro"
    DERIVATIVES = "Derivatives"
    CORRELATION = "Correlation"
    VOLATILITY = "Volatility"
    EVENTS = "Events"
    SECTOR_RS = "Sector RS"
    ON_CHAIN = "On-Chain"
    SENTIMENT = "Sentiment"


class WeightProfile(StrEnum):
    """Named weight tables selected by market regime."""

    TRENDING = "Trending"
    CHOPPY = "Choppy"
    HIGH_VOL = "High-vol"


def _normalize(raw: dict[ScoringCategory, float]) -> dict[ScoringCategory, float]:
    """Scale weights to sum to exactly 100, filling missing categories with 0."""
    merged = {cat: raw.get(cat, 0.0) for cat in ScoringCategory}
    total = sum(merged.values())
    if total <= 0:
        msg = "Cannot normalize empty weight map"
        raise ValueError(msg)
    scaled = {cat: (value / total) * 100.0 for cat, value in merged.items()}
    rounded = {cat: round(value, 2) for cat, value in scaled.items()}
    drift = 100.0 - sum(rounded.values())
    if rounded:
        first = next(iter(rounded))
        rounded[first] = round(rounded[first] + drift, 2)
    return rounded


# Core 7 relative shares (Structure 25 / Momentum 20 / Trend 15 / Risk 15 /
# Volume 10 / Macro 10 / Derivatives 5) of ~80–85; residual ~15–20 for extras.
DEFAULT_WEIGHTS: dict[ScoringCategory, float] = _normalize(
    {
        ScoringCategory.STRUCTURE: 25.0,
        ScoringCategory.MOMENTUM: 20.0,
        ScoringCategory.TREND: 15.0,
        ScoringCategory.RISK: 15.0,
        ScoringCategory.VOLUME: 10.0,
        ScoringCategory.MACRO: 10.0,
        ScoringCategory.DERIVATIVES: 5.0,
        ScoringCategory.CORRELATION: 3.5,
        ScoringCategory.VOLATILITY: 3.5,
        ScoringCategory.EVENTS: 3.5,
        ScoringCategory.SECTOR_RS: 3.5,
        ScoringCategory.ON_CHAIN: 3.0,
        ScoringCategory.SENTIMENT: 3.0,
    }
)

REGIME_WEIGHT_PROFILES: dict[WeightProfile, dict[ScoringCategory, float]] = {
    WeightProfile.TRENDING: _normalize(
        {
            ScoringCategory.TREND: 22.0,
            ScoringCategory.STRUCTURE: 20.0,
            ScoringCategory.MOMENTUM: 18.0,
            ScoringCategory.VOLUME: 8.0,
            ScoringCategory.RISK: 8.0,
            ScoringCategory.MACRO: 6.0,
            ScoringCategory.DERIVATIVES: 5.0,
            ScoringCategory.CORRELATION: 2.0,
            ScoringCategory.VOLATILITY: 2.0,
            ScoringCategory.EVENTS: 2.0,
            ScoringCategory.SECTOR_RS: 3.0,
            ScoringCategory.ON_CHAIN: 2.0,
            ScoringCategory.SENTIMENT: 2.0,
        }
    ),
    WeightProfile.CHOPPY: _normalize(
        {
            ScoringCategory.TREND: 8.0,
            ScoringCategory.STRUCTURE: 18.0,
            ScoringCategory.MOMENTUM: 12.0,
            ScoringCategory.VOLUME: 10.0,
            ScoringCategory.RISK: 16.0,
            ScoringCategory.MACRO: 8.0,
            ScoringCategory.DERIVATIVES: 6.0,
            ScoringCategory.CORRELATION: 4.0,
            ScoringCategory.VOLATILITY: 8.0,
            ScoringCategory.EVENTS: 3.0,
            ScoringCategory.SECTOR_RS: 3.0,
            ScoringCategory.ON_CHAIN: 2.0,
            ScoringCategory.SENTIMENT: 2.0,
        }
    ),
    WeightProfile.HIGH_VOL: _normalize(
        {
            ScoringCategory.TREND: 8.0,
            ScoringCategory.STRUCTURE: 10.0,
            ScoringCategory.MOMENTUM: 10.0,
            ScoringCategory.VOLUME: 8.0,
            ScoringCategory.RISK: 18.0,
            ScoringCategory.MACRO: 12.0,
            ScoringCategory.DERIVATIVES: 8.0,
            ScoringCategory.CORRELATION: 4.0,
            ScoringCategory.VOLATILITY: 10.0,
            ScoringCategory.EVENTS: 6.0,
            ScoringCategory.SECTOR_RS: 2.0,
            ScoringCategory.ON_CHAIN: 2.0,
            ScoringCategory.SENTIMENT: 2.0,
        }
    ),
}


def validate_weights(weights: dict[ScoringCategory, float]) -> None:
    """Ensure category weights sum to 100.

    Args:
        weights: Category-to-weight mapping.

    Raises:
        ValueError: If weights do not sum to 100.
    """
    total = sum(weights.values())
    if abs(total - 100.0) > 0.01:
        msg = f"Category weights must sum to 100, got {total}"
        raise ValueError(msg)


def resolve_weight_profile(
    regime: str,
    *,
    vix: float | None = None,
) -> WeightProfile:
    """Map RegimeEngine labels (+ optional VIX) to a weight profile.

    TRENDING → Trending; RANGING/QUIET → Choppy; VOLATILE and/or VIX≥25 → High-vol.
    """
    if regime == "Volatile" or (vix is not None and vix >= 25):
        return WeightProfile.HIGH_VOL
    if regime in {"Ranging", "Quiet"}:
        return WeightProfile.CHOPPY
    return WeightProfile.TRENDING


validate_weights(DEFAULT_WEIGHTS)
for _profile, _weights in REGIME_WEIGHT_PROFILES.items():
    validate_weights(_weights)
