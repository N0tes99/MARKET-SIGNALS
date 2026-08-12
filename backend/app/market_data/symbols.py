"""Tracked assets, asset classes, and exchange symbol mappings."""

import re
from enum import StrEnum
from typing import Final

# ---------------------------------------------------------------------------
# Asset classes
# ---------------------------------------------------------------------------


class AssetClass(StrEnum):
    """Broad asset category for routing market data providers."""

    CRYPTO = "crypto"
    STOCK = "stock"
    ETF = "etf"


# ---------------------------------------------------------------------------
# Watchlist (single source of truth)
# ---------------------------------------------------------------------------

CRYPTO_SYMBOLS: Final[tuple[str, ...]] = (
    "BTC",
    "ETH",
    "SOL",
    "SUI",
    "XRP",
    "ADA",
    "AVAX",
    "LINK",
    "DOGE",
    "DOT",
    "LTC",
    "ATOM",
    "NEAR",
    "ARB",
    "APT",
    "INJ",
    "TAO",
    "WIF",
    "PEPE",
    "RENDER",
    "FET",
    "TIA",
    "SEI",
    "JUP",
    "OP",
)

ETF_SYMBOLS: Final[tuple[str, ...]] = (
    "SPY",
    "QQQ",
    "IWM",
    "VOO",
    "DIA",
    "ARKK",
    "SOXL",
    "SMH",
    "IBIT",
    "XLE",
    "XBI",
    "TQQQ",
)

STOCK_SYMBOLS: Final[tuple[str, ...]] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "AMZN",
    "TSLA",
    "AMD",
    "NFLX",
    "NOW",
    "CRM",
    "PLTR",
    "COIN",
    "SMCI",
    "MSTR",
    "HOOD",
    "RKLB",
    "IONQ",
    "ARM",
    "SHOP",
    "SNOW",
    "UBER",
    "RBLX",
)

TRACKED_SYMBOLS: Final[tuple[str, ...]] = CRYPTO_SYMBOLS + ETF_SYMBOLS + STOCK_SYMBOLS
TRACKED_SYMBOLS_SET: frozenset[str] = frozenset(TRACKED_SYMBOLS)

ASSET_CLASS_MAP: dict[str, AssetClass] = {
    **dict.fromkeys(CRYPTO_SYMBOLS, AssetClass.CRYPTO),
    **dict.fromkeys(ETF_SYMBOLS, AssetClass.ETF),
    **dict.fromkeys(STOCK_SYMBOLS, AssetClass.STOCK),
}

# ---------------------------------------------------------------------------
# Crypto exchange mappings
# ---------------------------------------------------------------------------

BINANCE_SYMBOL_MAP: dict[str, str] = {s: f"{s}USDT" for s in CRYPTO_SYMBOLS}

KRAKEN_PAIR_MAP: dict[str, str] = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "SUI": "SUIUSD",
    "XRP": "XRPUSD",
    "ADA": "ADAUSD",
    "AVAX": "AVAXUSD",
    "LINK": "LINKUSD",
    "DOGE": "XDGUSD",
    "DOT": "DOTUSD",
    "LTC": "LTCUSD",
    "ATOM": "ATOMUSD",
    "NEAR": "NEARUSD",
    "ARB": "ARBUSD",
    "APT": "APTUSD",
    "INJ": "INJUSD",
    "TAO": "TAOUSD",
    "WIF": "WIFUSD",
    "PEPE": "PEPEUSD",
    "RENDER": "RENDERUSD",
    "FET": "FETUSD",
    "TIA": "TIAUSD",
    "SEI": "SEIUSD",
    "JUP": "JUPUSD",
    "OP": "OPUSD",
}

TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


_US_EQUITY_TICKER = re.compile(r"^[A-Z]{1,5}$")


def is_tracked(symbol: str) -> bool:
    """Return True if the symbol is on the dashboard watchlist."""
    return symbol.upper() in TRACKED_SYMBOLS_SET


def looks_like_us_equity_ticker(symbol: str) -> bool:
    """True for a 1–5 letter US ticker that is not a tracked crypto symbol.

    Used by Surface 4 / Yahoo so seed names (CRDO, ALAB, …) can fetch OHLCV
    without being added to Surface 1 ``TRACKED_SYMBOLS``.
    """
    normalized = symbol.upper().strip()
    if not _US_EQUITY_TICKER.fullmatch(normalized):
        return False
    return normalized not in ASSET_CLASS_MAP or ASSET_CLASS_MAP[normalized] != AssetClass.CRYPTO


def get_asset_class(symbol: str) -> AssetClass:
    """Return the asset class for a tracked symbol."""
    normalized = symbol.upper()
    if normalized not in ASSET_CLASS_MAP:
        msg = f"Symbol '{normalized}' is not tracked"
        raise ValueError(msg)
    return ASSET_CLASS_MAP[normalized]


def is_crypto(symbol: str) -> bool:
    """Return True if symbol is a cryptocurrency."""
    return get_asset_class(symbol) == AssetClass.CRYPTO


def to_binance_symbol(symbol: str) -> str:
    """Convert a crypto symbol to a Binance trading pair."""
    normalized = symbol.upper()
    if normalized not in BINANCE_SYMBOL_MAP:
        msg = f"Symbol '{normalized}' is not a supported crypto pair"
        raise ValueError(msg)
    return BINANCE_SYMBOL_MAP[normalized]


def to_binance_interval(timeframe: str) -> str:
    """Convert a timeframe string to a Binance interval."""
    if timeframe not in TIMEFRAME_MAP:
        msg = f"Timeframe '{timeframe}' is not supported"
        raise ValueError(msg)
    return TIMEFRAME_MAP[timeframe]


def to_kraken_pair(symbol: str) -> str:
    """Convert a crypto symbol to a Kraken spot pair name."""
    normalized = symbol.upper()
    if normalized not in KRAKEN_PAIR_MAP:
        msg = f"Symbol '{normalized}' is not supported on Kraken"
        raise ValueError(msg)
    return KRAKEN_PAIR_MAP[normalized]
