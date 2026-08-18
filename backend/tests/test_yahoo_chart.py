"""Yahoo chart timeframe helpers (no live Yahoo calls)."""

from datetime import UTC

import pandas as pd

from app.market_data.providers.yahoo import (
    _YF_PERIOD_MAP,
    timestamp_to_utc,
    yahoo_history_period,
)


def test_intraday_periods_cover_weekends() -> None:
    assert _YF_PERIOD_MAP["1m"] == "2d"
    assert _YF_PERIOD_MAP["5m"] == "5d"
    assert _YF_PERIOD_MAP["15m"] == "5d"


def test_naive_eastern_bar_converts_to_utc() -> None:
    # Regular-session open 09:30 Eastern in August is UTC-4.
    dt = timestamp_to_utc(pd.Timestamp("2026-08-12 09:30:00"))
    assert dt.tzinfo is not None
    assert dt.astimezone(UTC).hour == 13


def test_aware_timestamp_converts_to_utc() -> None:
    ts = pd.Timestamp("2026-08-12 13:30:00", tz="UTC")
    dt = timestamp_to_utc(ts)
    assert dt.astimezone(UTC).hour == 13


def test_scanner_sized_1h_does_not_request_60d() -> None:
    assert yahoo_history_period("1h", 20) != "60d"
    assert yahoo_history_period("1h", 20) == "5d"
    assert yahoo_history_period("1d", 28) != "2y"


def test_chart_sized_limits_keep_long_history() -> None:
    assert yahoo_history_period("1h", 200) == _YF_PERIOD_MAP["1h"] == "60d"
    assert yahoo_history_period("1d", 200) == _YF_PERIOD_MAP["1d"] == "2y"
    assert yahoo_history_period("15m", 96) == "5d"
