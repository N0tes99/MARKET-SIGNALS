"""Quote / price-feed tests."""

import time
from threading import Event

from app.api.tracked import TRACKED_SYMBOLS
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.schemas.quotes import AssetQuote
from app.services import quote_service
from app.services.quote_service import build_quote, load_all_quotes


def _md() -> MarketDataService:
    return MarketDataService(provider=MockMarketDataProvider())


def test_build_quote_available() -> None:
    quote = build_quote(_md(), "BTC")
    assert quote.symbol == "BTC"
    assert quote.available is True
    assert quote.price is not None
    assert quote.price > 0


def test_load_all_quotes_includes_tracked() -> None:
    quotes = load_all_quotes(_md())
    symbols = {q.symbol for q in quotes}
    assert "BTC" in symbols
    assert "SPY" in symbols
    assert all(q.price is None or q.price >= 0 for q in quotes)


def test_progressive_quotes_return_before_tickers(monkeypatch) -> None:
    quote_service._QUOTES_CACHE.clear()
    release = Event()

    def blocker(_market_data, symbol: str) -> AssetQuote:
        release.wait(timeout=5)
        return AssetQuote(symbol=symbol, available=False)

    monkeypatch.setattr(quote_service, "build_quote", blocker)
    started = time.perf_counter()
    quotes = load_all_quotes(_md(), progressive=True)
    elapsed = time.perf_counter() - started
    release.set()
    assert elapsed < 0.5
    assert len(quotes) == len(TRACKED_SYMBOLS)
    assert all(quote.available is False for quote in quotes)
