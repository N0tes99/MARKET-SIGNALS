"""Derivatives-only provider — Binance → Bybit → OKX via shared depth stack."""

from __future__ import annotations

import pandas as pd

from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.bybit_derivatives import fetch_derivatives_depth
from app.market_data.types import DerivativesSnapshot, TickerSnapshot


class DepthDerivativesProvider(MarketDataProvider):
    """Fills funding/OI when spot providers (Kraken) leave derivatives blank.

    OHLCV/ticker are intentionally unsupported — FallbackProvider skips this
    provider for those calls and keeps using Kraken/Binance/Yahoo.
    """

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        del symbol, timeframe, limit
        msg = "DepthDerivativesProvider is derivatives-only"
        raise RuntimeError(msg)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        del symbol
        msg = "DepthDerivativesProvider is derivatives-only"
        raise RuntimeError(msg)

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        depth = fetch_derivatives_depth(symbol)
        if depth is None:
            return DerivativesSnapshot(
                symbol=symbol.upper(),
                funding_rate=None,
                open_interest=None,
                mark_price=None,
            )
        return DerivativesSnapshot(
            symbol=symbol.upper(),
            funding_rate=depth.funding_rate,
            open_interest=depth.open_interest,
            mark_price=depth.mark_price,
        )
