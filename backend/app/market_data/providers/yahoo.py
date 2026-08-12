"""Yahoo Finance market data provider for stocks and ETFs."""

from datetime import datetime

import pandas as pd
import yfinance as yf

from app.market_data.normalizer import STANDARD_COLUMNS
from app.market_data.symbols import AssetClass, get_asset_class
from app.market_data.types import DerivativesSnapshot, TickerSnapshot

_YF_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "1h",  # Yahoo has no native 4h; use 1h bars
    "1d": "1d",
}

# Intraday Yahoo windows must survive weekends / after-hours or charts go empty.
_YF_PERIOD_MAP: dict[str, str] = {
    "1m": "2d",
    "5m": "5d",
    "15m": "5d",
    "1h": "60d",
    "4h": "60d",
    "1d": "2y",
}

_INTRADAY = frozenset({"1m", "5m", "15m"})


def timestamp_to_utc(value: object) -> datetime:
    """Normalize Yahoo timestamps to UTC (naive bars are US/Eastern session)."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York", ambiguous=True, nonexistent="shift_forward")
    return ts.tz_convert("UTC").to_pydatetime()


class YahooFinanceProvider:
    """Fetch OHLCV and quotes for US stocks and ETFs via yfinance."""

    def _resolve_yahoo_symbol(self, symbol: str) -> str:
        """Accept watchlist equities plus index tickers like ^VIX."""
        normalized = symbol.upper()
        if normalized.startswith("^"):
            return normalized
        asset_class = get_asset_class(normalized)
        if asset_class not in {AssetClass.STOCK, AssetClass.ETF}:
            msg = f"Symbol '{normalized}' is not a stock or ETF"
            raise ValueError(msg)
        return normalized

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Return OHLCV history from Yahoo Finance."""
        normalized = self._resolve_yahoo_symbol(symbol)
        interval = _YF_INTERVAL_MAP.get(timeframe)
        if interval is None:
            msg = f"Timeframe '{timeframe}' is not supported for equities"
            raise ValueError(msg)

        period = _YF_PERIOD_MAP.get(timeframe, "1y")
        ticker = yf.Ticker(normalized)
        raw = ticker.history(
            period=period,
            interval=interval,
            auto_adjust=True,
            prepost=timeframe in _INTRADAY,
        )

        if raw.empty:
            msg = f"No Yahoo Finance data for {normalized}"
            raise RuntimeError(msg)

        raw = raw.tail(limit).reset_index()
        ts_col = "Datetime" if "Datetime" in raw.columns else "Date"

        rows = [
            {
                "timestamp": timestamp_to_utc(row[ts_col]),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
            for _, row in raw.iterrows()
        ]

        return pd.DataFrame(rows, columns=STANDARD_COLUMNS)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Return the latest equity quote."""
        normalized = self._resolve_yahoo_symbol(symbol)
        ticker = yf.Ticker(normalized)
        info = ticker.fast_info
        price = float(info.last_price)

        return TickerSnapshot(
            symbol=normalized,
            price=price,
            timestamp=datetime.now(UTC),
        )

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Equities have no derivatives feed in this provider."""
        return DerivativesSnapshot(
            symbol=symbol.upper(),
            funding_rate=None,
            open_interest=None,
            mark_price=None,
        )
