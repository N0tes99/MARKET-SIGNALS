"""Tests for product-level market data freshness / degraded mode."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.market_data.freshness import DataFreshnessTracker
from app.market_data.service import MarketDataService
from app.market_data.types import TickerSnapshot


def test_freshness_not_degraded_after_success() -> None:
    tracker = DataFreshnessTracker(stale_seconds=900, failure_threshold=3)
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    tracker.record_success("BTC", fetched_at=now)
    snap = tracker.status("BTC", now=now + timedelta(seconds=60))
    assert snap.degraded is False
    assert snap.reason is None
    assert snap.age_seconds == pytest.approx(60.0)


def test_freshness_degraded_when_age_exceeds_threshold() -> None:
    tracker = DataFreshnessTracker(stale_seconds=900, failure_threshold=3)
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    tracker.record_success("ETH", fetched_at=now)
    snap = tracker.status("ETH", now=now + timedelta(seconds=901))
    assert snap.degraded is True
    assert snap.reason == "stale_data"
    assert snap.age_seconds == pytest.approx(901.0)


def test_freshness_degraded_after_repeated_failures() -> None:
    tracker = DataFreshnessTracker(stale_seconds=900, failure_threshold=3)
    tracker.record_failure("SOL")
    tracker.record_failure("SOL")
    assert tracker.status("SOL").degraded is False
    tracker.record_failure("SOL")
    snap = tracker.status("SOL")
    assert snap.degraded is True
    assert snap.reason == "provider_errors"
    assert snap.consecutive_failures == 3


def test_freshness_success_resets_failures() -> None:
    tracker = DataFreshnessTracker(stale_seconds=900, failure_threshold=3)
    for _ in range(3):
        tracker.record_failure("SUI")
    assert tracker.status("SUI").degraded is True
    tracker.record_success("SUI", fetched_at=datetime.now(UTC))
    assert tracker.status("SUI").degraded is False
    assert tracker.status("SUI").consecutive_failures == 0


def test_freshness_any_degraded() -> None:
    tracker = DataFreshnessTracker(stale_seconds=900, failure_threshold=2)
    tracker.record_success("BTC", fetched_at=datetime.now(UTC))
    assert tracker.any_degraded(["BTC", "ETH"]) is False
    tracker.record_failure("ETH")
    tracker.record_failure("ETH")
    assert tracker.any_degraded(["BTC", "ETH"]) is True


class _FailingProvider:
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        raise RuntimeError("provider down")

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        raise RuntimeError("provider down")

    def get_derivatives(self, symbol: str):
        raise RuntimeError("provider down")


class _EmptyProvider:
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        return pd.DataFrame()

    def get_ticker(self, symbol: str) -> TickerSnapshot | None:
        return None

    def get_derivatives(self, symbol: str):
        raise RuntimeError("unused")


def test_market_data_service_records_provider_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.market_data import service as md_service
    from app.market_data.freshness import freshness_tracker

    freshness_tracker.reset()
    md_service._OHLCV_CACHE.clear()
    svc = MarketDataService(provider=_FailingProvider())  # type: ignore[arg-type]

    assert svc.safe_get_ohlcv("BTC") is None
    assert svc.safe_get_ohlcv("BTC") is None
    assert svc.safe_get_ohlcv("BTC") is None
    snap = freshness_tracker.status("BTC")
    assert snap.degraded is True
    assert snap.reason == "provider_errors"
    assert snap.consecutive_failures >= 3


def test_market_data_service_records_empty_as_failure() -> None:
    from app.market_data import service as md_service
    from app.market_data.freshness import freshness_tracker

    freshness_tracker.reset()
    md_service._OHLCV_CACHE.clear()
    md_service._TICKER_CACHE.clear()
    svc = MarketDataService(provider=_EmptyProvider())  # type: ignore[arg-type]

    assert svc.safe_get_ohlcv("ETH") is None
    with pytest.raises(ValueError, match="Empty ticker"):
        svc.get_ticker("ETH")
    assert freshness_tracker.status("ETH").consecutive_failures >= 2
