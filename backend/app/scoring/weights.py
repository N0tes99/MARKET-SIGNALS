"""Default scoring category weights."""

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


DEFAULT_WEIGHTS: dict[ScoringCategory, float] = {
    ScoringCategory.TREND: 14.0,
    ScoringCategory.MOMENTUM: 11.0,
    ScoringCategory.VOLUME: 7.0,
    ScoringCategory.STRUCTURE: 14.0,
    ScoringCategory.RISK: 12.0,
    ScoringCategory.MACRO: 6.0,
    ScoringCategory.DERIVATIVES: 8.0,
    ScoringCategory.CORRELATION: 5.0,
    ScoringCategory.VOLATILITY: 5.0,
    ScoringCategory.EVENTS: 5.0,
    ScoringCategory.SECTOR_RS: 5.0,
    ScoringCategory.ON_CHAIN: 5.0,
    ScoringCategory.SENTIMENT: 3.0,
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


validate_weights(DEFAULT_WEIGHTS)
