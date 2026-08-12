"""Binance public REST API market data provider."""

import os
from datetime import UTC, datetime

import httpx
import pandas as pd

from app.config import settings
from app.market_data.normalizer import STANDARD_COLUMNS
from app.market_data.symbols import to_binance_interval, to_binance_symbol
from app.market_data.types import DerivativesSnapshot, TickerSnapshot

# Geo/auth blocks — fail fast so FallbackProvider can try Kraken.
_SOFT_FAIL_STATUS = frozenset({403, 418, 451})


def use_binance() -> bool:
    """False on Render (US IPs get 451). Opt in with BINANCE_ENABLED=true."""
    raw = os.environ.get("BINANCE_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no"}:
        return False
    if raw in {"1", "true", "yes"}:
        return True
    if os.environ.get("RENDER"):
        return False
    return bool(settings.binance_enabled)


class BinanceBlockedError(RuntimeError):
    """Binance rejected the request (geo-block / ban); try next provider."""


def _raise_for_binance(response: httpx.Response) -> None:
    if response.status_code in _SOFT_FAIL_STATUS:
        raise BinanceBlockedError(f"Binance HTTP {response.status_code}")
    response.raise_for_status()


class BinanceProvider:
    """Fetch market data from Binance spot and futures public APIs."""

    def __init__(
        self,
        spot_base_url: str | None = None,
        futures_base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Initialize with optional custom base URLs."""
        self._spot_base_url = spot_base_url or settings.binance_spot_url
        self._futures_base_url = futures_base_url or settings.binance_futures_url
        self._timeout = timeout

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV klines from Binance spot API."""
        pair = to_binance_symbol(symbol)
        interval = to_binance_interval(timeframe)

        url = f"{self._spot_base_url}/api/v3/klines"
        params = {"symbol": pair, "interval": interval, "limit": limit}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)
            _raise_for_binance(response)
            raw = response.json()

        rows = [
            {
                "timestamp": datetime.fromtimestamp(candle[0] / 1000, tz=UTC),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            }
            for candle in raw
        ]

        return pd.DataFrame(rows, columns=STANDARD_COLUMNS)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch latest price from Binance spot API."""
        pair = to_binance_symbol(symbol)
        url = f"{self._spot_base_url}/api/v3/ticker/price"
        params = {"symbol": pair}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)
            _raise_for_binance(response)
            data = response.json()

        return TickerSnapshot(
            symbol=symbol.upper(),
            price=float(data["price"]),
            timestamp=datetime.now(UTC),
        )

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Fetch funding rate and open interest from Binance futures API."""
        pair = to_binance_symbol(symbol)

        with httpx.Client(timeout=self._timeout) as client:
            premium_url = f"{self._futures_base_url}/fapi/v1/premiumIndex"
            premium_resp = client.get(premium_url, params={"symbol": pair})
            _raise_for_binance(premium_resp)
            premium = premium_resp.json()

            oi_url = f"{self._futures_base_url}/fapi/v1/openInterest"
            oi_resp = client.get(oi_url, params={"symbol": pair})
            _raise_for_binance(oi_resp)
            oi = oi_resp.json()

        return DerivativesSnapshot(
            symbol=symbol.upper(),
            funding_rate=float(premium["lastFundingRate"]),
            open_interest=float(oi["openInterest"]),
            mark_price=float(premium["markPrice"]),
        )
