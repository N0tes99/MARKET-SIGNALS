"""Kraken public REST API market data provider (US-friendly fallback)."""

from datetime import UTC, datetime

import httpx
import pandas as pd

from app.config import settings
from app.market_data.normalizer import STANDARD_COLUMNS
from app.market_data.types import DerivativesSnapshot, TickerSnapshot

from app.market_data.symbols import to_kraken_pair

KRAKEN_INTERVAL_MAP: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


class KrakenProvider:
    """Fetch market data from Kraken public API."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        """Initialize with optional custom base URL."""
        self._base_url = base_url or settings.kraken_api_url
        self._timeout = timeout

    def _pair(self, symbol: str) -> str:
        """Map dashboard symbol to Kraken pair name."""
        return to_kraken_pair(symbol)

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV from Kraken public OHLC endpoint."""
        pair = self._pair(symbol)
        interval = KRAKEN_INTERVAL_MAP.get(timeframe)
        if interval is None:
            msg = f"Timeframe '{timeframe}' is not supported on Kraken"
            raise ValueError(msg)

        url = f"{self._base_url}/0/public/OHLC"
        params = {"pair": pair, "interval": interval}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if payload.get("error"):
            msg = f"Kraken API error: {payload['error']}"
            raise RuntimeError(msg)

        result_key = next(iter(payload["result"]))
        raw = payload["result"][result_key][-limit:]

        rows = [
            {
                "timestamp": datetime.fromtimestamp(candle[0], tz=UTC),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[6]),
            }
            for candle in raw
        ]

        return pd.DataFrame(rows, columns=STANDARD_COLUMNS)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch latest ticker from Kraken."""
        pair = self._pair(symbol)
        url = f"{self._base_url}/0/public/Ticker"
        params = {"pair": pair}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        result_key = next(iter(payload["result"]))
        price = float(payload["result"][result_key]["c"][0])

        return TickerSnapshot(
            symbol=symbol.upper(),
            price=price,
            timestamp=datetime.now(UTC),
        )

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Kraken spot provider does not supply derivatives; return empty snapshot."""
        return DerivativesSnapshot(
            symbol=symbol.upper(),
            funding_rate=None,
            open_interest=None,
            mark_price=None,
        )
