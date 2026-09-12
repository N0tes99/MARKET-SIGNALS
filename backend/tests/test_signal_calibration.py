"""Opportunity score is not a calibrated win probability."""

import pytest

from app.engines.paper_agent.broker import size_from_stop
from app.scoring.grading import calibrated_win_prob, compute_expected_value


def test_calibrated_win_prob_is_conservative() -> None:
    assert calibrated_win_prob(0) == pytest.approx(0.22)
    assert calibrated_win_prob(70) == pytest.approx(0.402)
    assert calibrated_win_prob(100) == pytest.approx(0.48)
    assert calibrated_win_prob(70) < 0.70


def test_compute_expected_value_does_not_treat_score_as_percent() -> None:
    # Old formula: 70/100 * 1.35 - 0.30 = 0.645. Conservative band is near 0 / negative.
    naive = (0.70 * 1.35) - 0.30
    actual = compute_expected_value(70.0, 1.35)
    assert actual < naive
    assert actual < 0.1
    # Stronger R:R still clears at grade B.
    assert compute_expected_value(70.0, 2.0) > 0


def test_size_from_stop_scales_with_stop_distance() -> None:
    tight = size_from_stop(cash=15_000.0, stop_loss_pct=3.0, cap_usd=2_500.0)
    wide = size_from_stop(cash=5_000.0, stop_loss_pct=5.0, cap_usd=2_500.0)
    assert tight == 2500.0  # 1% of 15k / 3% = 5k, capped
    assert wide == 1000.0
