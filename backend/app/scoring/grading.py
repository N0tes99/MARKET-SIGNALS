"""Trade grading utilities."""

from enum import StrEnum


class TradeState(StrEnum):
    """Trade lifecycle state."""

    IGNORE = "IGNORE"
    WATCH = "WATCH"
    EXECUTE = "EXECUTE"
    MANAGE = "MANAGE"
    EXIT = "EXIT"


def score_to_grade(score: float) -> str:
    """Map a 0–100 score to a letter grade."""
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def compute_expected_value(opportunity_score: float, risk_reward_ratio: float) -> float:
    """Estimate expected value from opportunity score and risk/reward.

    Returns a unitless EV estimate where positive values favor the trade.
    """
    win_prob = opportunity_score / 100
    lose_prob = 1 - win_prob
    return round((win_prob * risk_reward_ratio) - lose_prob, 3)
