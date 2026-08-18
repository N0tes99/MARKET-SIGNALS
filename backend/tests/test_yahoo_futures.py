"""Yahoo continuous futures (=F) resolve without swallowing equities or spot crypto."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from app.engines.runner_engine.scoring.yahoo_futures_quote import (
    clear_yahoo_futures_quote_cache,
    fetch_yahoo_futures_quote,
)
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.symbols import (
    AssetClass,
    get_asset_class,
    is_tracked,
    looks_like_us_equity_ticker,
    looks_like_yahoo_future,
    resolve_asset_class,
)


def test_es_f_resolves_as_yahoo_future() -> None:
    yahoo = YahooFinanceProvider()
    assert yahoo._resolve_yahoo_symbol("ES=F") == "ES=F"
    assert yahoo._resolve_yahoo_symbol("es=f") == "ES=F"
    assert looks_like_yahoo_future("ES=F") is True
    assert looks_like_us_equity_ticker("ES=F") is False
    assert get_asset_class("ES=F") == AssetClass.FUTURES
    assert resolve_asset_class("ES=F") == AssetClass.FUTURES
    assert is_tracked("ES=F") is False


def test_equity_ticker_still_resolves() -> None:
    yahoo = YahooFinanceProvider()
    assert yahoo._resolve_yahoo_symbol("CRDO") == "CRDO"
    assert yahoo._resolve_yahoo_symbol("AAPL") == "AAPL"
    assert looks_like_us_equity_ticker("CRDO") is True
    assert looks_like_yahoo_future("CRDO") is False
    assert resolve_asset_class("CRDO") == AssetClass.STOCK


def test_btc_spot_is_not_a_yahoo_future() -> None:
    yahoo = YahooFinanceProvider()
    assert looks_like_yahoo_future("BTC") is False
    assert looks_like_us_equity_ticker("BTC") is False
    assert get_asset_class("BTC") == AssetClass.CRYPTO
    assert resolve_asset_class("BTC") == AssetClass.CRYPTO
    with pytest.raises(ValueError, match="not a stock or ETF"):
        yahoo._resolve_yahoo_symbol("BTC")
    assert yahoo._resolve_yahoo_symbol("BTC=F") == "BTC=F"
    assert get_asset_class("BTC=F") == AssetClass.FUTURES


def test_1h_limit_20_does_not_request_60d(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class _Ticker:
        def history(self, period, interval, auto_adjust, prepost):
            captured["period"] = period
            captured["interval"] = interval
            idx = pd.date_range("2026-08-14", periods=20, freq="h", tz="UTC")
            frame = pd.DataFrame(
                {
                    "Open": 100.0,
                    "High": 101.0,
                    "Low": 99.0,
                    "Close": 100.5,
                    "Volume": 1000.0,
                },
                index=idx,
            )
            frame.index.name = "Datetime"
            return frame

    monkeypatch.setattr("app.market_data.providers.yahoo.yf.Ticker", lambda symbol: _Ticker())
    df = YahooFinanceProvider().get_ohlcv("ES=F", "1h", limit=20)
    assert captured["period"] != "60d"
    assert captured["period"] == "5d"
    assert captured["interval"] == "1h"
    assert len(df) == 20


def test_futures_quote_uses_fast_info_not_info(monkeypatch) -> None:
    class _Ticker:
        @property
        def info(self):
            raise AssertionError("ticker.info must not be called")

        fast_info = SimpleNamespace(
            last_price=5400.0,
            previous_close=5375.0,
            last_volume=180_000.0,
        )

    monkeypatch.setattr(
        "app.engines.runner_engine.scoring.yahoo_futures_quote.yf.Ticker",
        lambda symbol: _Ticker(),
    )
    clear_yahoo_futures_quote_cache()
    snap = fetch_yahoo_futures_quote("ES=F")
    assert snap.fetched_ok is True
    assert snap.last == pytest.approx(5400.0)
    assert snap.change_pct == pytest.approx((5400.0 / 5375.0 - 1.0) * 100.0)
    assert snap.volume == pytest.approx(180_000.0)
    assert snap.open_interest is None
    assert snap.expire_date is None
    clear_yahoo_futures_quote_cache()
