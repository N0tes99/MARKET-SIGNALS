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


def blend_expected_value(
    formula_ev: float,
    risk_reward_ratio: float,
    hit_rate_pct: float,
    avg_return_pct: float,
    sample_count: int,
    *,
    min_samples: int = 3,
    history_weight: float = 0.4,
) -> float:
    """Blend formula EV with historical hit-rate / avg return when enough samples.

    Falls back to ``formula_ev`` when ``sample_count < min_samples``.
    Historical EV uses hit rate as win probability against the same R:R, then
    nudges toward realized avg return (scaled into EV units).
    """
    if sample_count < min_samples:
        return formula_ev

    win_prob = max(0.0, min(hit_rate_pct / 100.0, 1.0))
    hist_rr_ev = (win_prob * risk_reward_ratio) - (1.0 - win_prob)
    # avg_return_pct is percent points (e.g. 1.5 == +1.5%); dampen into EV scale
    hist_return_ev = avg_return_pct / 100.0 * risk_reward_ratio
    historical_ev = 0.7 * hist_rr_ev + 0.3 * hist_return_ev
    blended = (1.0 - history_weight) * formula_ev + history_weight * historical_ev
    return round(blended, 3)
