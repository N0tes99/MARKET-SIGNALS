"""Route market data requests to crypto or equity providers."""

import pandas as pd

from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.symbols import ASSET_CLASS_MAP, AssetClass
from app.market_data.types import DerivativesSnapshot, TickerSnapshot


class AssetRouterProvider:
    """Dispatch OHLCV/ticker requests by asset class."""

    def __init__(
        self,
        crypto: MarketDataProvider,
        equities: MarketDataProvider | None = None,
    ) -> None:
        self._crypto = crypto
        self._equities = equities or YahooFinanceProvider()

    def _provider_for(self, symbol: str) -> MarketDataProvider:
        normalized = symbol.upper()
        if normalized in ASSET_CLASS_MAP and ASSET_CLASS_MAP[normalized] == AssetClass.CRYPTO:
            return self._crypto
        return self._equities

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        return self._provider_for(symbol).get_ohlcv(symbol, timeframe, limit)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        return self._provider_for(symbol).get_ticker(symbol)

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        return self._provider_for(symbol).get_derivatives(symbol)
