"""Yahoo may fetch Surface 4 tickers without adding them to the watchlist."""

from __future__ import annotations

import pytest

from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.symbols import (
    AssetClass,
    get_asset_class,
    is_tracked,
    looks_like_us_equity_ticker,
    resolve_asset_class,
)


def test_looks_like_us_equity_ticker() -> None:
    assert looks_like_us_equity_ticker("CRDO") is True
    assert looks_like_us_equity_ticker("ALAB") is True
    assert looks_like_us_equity_ticker("ZZZZ") is True
    assert looks_like_us_equity_ticker("BTC") is False
    assert looks_like_us_equity_ticker("TOOLONG") is False
    assert looks_like_us_equity_ticker("") is False


def test_crdo_not_on_surface1() -> None:
    assert is_tracked("CRDO") is False
    with pytest.raises(ValueError, match="not tracked"):
        get_asset_class("CRDO")
    assert resolve_asset_class("CRDO") == AssetClass.STOCK
    assert resolve_asset_class("BTC") == AssetClass.CRYPTO
    assert resolve_asset_class("TOOLONG") is None


def test_yahoo_resolves_untracked_and_rejects_crypto() -> None:
    yahoo = YahooFinanceProvider()
    assert yahoo._resolve_yahoo_symbol("CRDO") == "CRDO"
    assert yahoo._resolve_yahoo_symbol("smci") == "SMCI"
    with pytest.raises(ValueError, match="not a stock or ETF"):
        yahoo._resolve_yahoo_symbol("BTC")
