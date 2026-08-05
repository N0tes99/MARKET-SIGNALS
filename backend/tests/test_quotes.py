"""Quote / price-feed tests."""

from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
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
