"""Radar Phase 3: QoQ acceleration + discovery gap vs valuation."""

import pandas as pd

from app.engines.runner_engine.scoring.yahoo_dims import (
    qoq_acceleration,
    score_discovery_gap,
    score_fundamental,
)
from app.engines.runner_engine.scoring.yahoo_snapshot import (
    YahooRunnerSnapshot,
    empty_yahoo_snapshot,
    quarterly_revenues_from_frame,
)


def test_qoq_acceleration_from_rising_quarters() -> None:
    latest, accel = qoq_acceleration((120.0, 90.0, 80.0))
    assert latest is not None and latest > 0.30
    assert accel is not None and accel > 0.15


def test_qoq_acceleration_needs_three_quarters() -> None:
    assert qoq_acceleration((120.0, 90.0)) == (None, None)


def test_quarterly_revenues_newest_first() -> None:
    frame = pd.DataFrame(
        [[80.0, 100.0, 120.0]],
        index=["Total Revenue"],
        columns=["2025-10-31", "2026-01-31", "2026-04-30"],
    )
    assert quarterly_revenues_from_frame(frame)[:3] == (120.0, 100.0, 80.0)


def test_fundamental_uses_qoq_acceleration() -> None:
    snap = YahooRunnerSnapshot(
        symbol="CRDO",
        fetched_ok=True,
        quarterly_revenue=(120.0, 90.0, 80.0),
    )
    dim = score_fundamental(snap)
    assert dim.data_quality == "good"
    assert any("QoQ acceleration" in line for line in dim.factors)
    assert any("Growth accelerating" in line for line in dim.factors)


def test_discovery_gap_cheap_growth_beats_priced_in() -> None:
    cheap = score_discovery_gap(
        YahooRunnerSnapshot(
            symbol="CRDO",
            fetched_ok=True,
            number_of_analysts=4,
            market_cap=1_200_000_000.0,
            revenue_growth=0.42,
            forward_pe=28.0,
            week52_change=0.08,
            quarterly_revenue=(120.0, 90.0, 80.0),
        )
    )
    rich = score_discovery_gap(
        YahooRunnerSnapshot(
            symbol="MEGA",
            fetched_ok=True,
            number_of_analysts=28,
            market_cap=250_000_000_000.0,
            revenue_growth=0.08,
            forward_pe=48.0,
            week52_change=1.20,
        )
    )
    assert cheap.data_quality == "good"
    assert rich.data_quality == "good"
    assert cheap.score > rich.score
    assert any("Growth ahead of valuation" in line for line in cheap.factors)
    assert any("Valuation already expanded" in line for line in rich.conflicts)
    assert any("Price already expanded" in line for line in rich.factors)


def test_empty_snapshot_still_missing_discovery() -> None:
    dim = score_discovery_gap(empty_yahoo_snapshot("CRDO"))
    assert dim.data_quality == "missing"
