"""Yahoo continuous futures (=F) resolve without swallowing equities or spot crypto."""

from __future__ import annotations

import pytest

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
