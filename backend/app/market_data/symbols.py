"""Tracked assets, asset classes, and exchange symbol mappings."""

import re
from dataclasses import dataclass
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
    FUTURES = "futures"


class FuturesGroup(StrEnum):
    """CME / traditional futures sector for the Yahoo continuous board."""

    INDEX = "index"
    ENERGY = "energy"
    METALS = "metals"
    RATES = "rates"
    FX = "fx"
    GRAINS = "grains"
    CRYPTO = "crypto"


@dataclass(frozen=True)
class FuturesSpec:
    """Yahoo continuous contract with display metadata."""

    symbol: str
    name: str
    group: FuturesGroup


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

# Yahoo continuous front-month (=F). Not on the Surface 1 dashboard watchlist.
FUTURES_CONTRACTS: Final[tuple[FuturesSpec, ...]] = (
    FuturesSpec("ES=F", "E-mini S&P 500", FuturesGroup.INDEX),
    FuturesSpec("NQ=F", "E-mini Nasdaq-100", FuturesGroup.INDEX),
    FuturesSpec("YM=F", "E-mini Dow", FuturesGroup.INDEX),
    FuturesSpec("RTY=F", "E-mini Russell 2000", FuturesGroup.INDEX),
    FuturesSpec("CL=F", "Crude Oil", FuturesGroup.ENERGY),
    FuturesSpec("NG=F", "Natural Gas", FuturesGroup.ENERGY),
    FuturesSpec("RB=F", "RBOB Gasoline", FuturesGroup.ENERGY),
    FuturesSpec("HO=F", "Heating Oil", FuturesGroup.ENERGY),
    FuturesSpec("GC=F", "Gold", FuturesGroup.METALS),
    FuturesSpec("SI=F", "Silver", FuturesGroup.METALS),
    FuturesSpec("HG=F", "Copper", FuturesGroup.METALS),
    FuturesSpec("PL=F", "Platinum", FuturesGroup.METALS),
    FuturesSpec("ZN=F", "10-Year T-Note", FuturesGroup.RATES),
    FuturesSpec("ZB=F", "30-Year T-Bond", FuturesGroup.RATES),
    FuturesSpec("ZF=F", "5-Year T-Note", FuturesGroup.RATES),
    FuturesSpec("6E=F", "Euro FX", FuturesGroup.FX),
    FuturesSpec("6J=F", "Japanese Yen", FuturesGroup.FX),
    FuturesSpec("6B=F", "British Pound", FuturesGroup.FX),
    FuturesSpec("ZC=F", "Corn", FuturesGroup.GRAINS),
    FuturesSpec("ZS=F", "Soybeans", FuturesGroup.GRAINS),
    FuturesSpec("ZW=F", "Wheat", FuturesGroup.GRAINS),
    FuturesSpec("BTC=F", "Bitcoin", FuturesGroup.CRYPTO),
    FuturesSpec("ETH=F", "Ether", FuturesGroup.CRYPTO),
    FuturesSpec("MBT=F", "Micro Bitcoin", FuturesGroup.CRYPTO),
)
FUTURES_SYMBOLS: Final[tuple[str, ...]] = tuple(c.symbol for c in FUTURES_CONTRACTS)
FUTURES_BY_SYMBOL: dict[str, FuturesSpec] = {c.symbol: c for c in FUTURES_CONTRACTS}

ASSET_CLASS_MAP: dict[str, AssetClass] = {
    **dict.fromkeys(CRYPTO_SYMBOLS, AssetClass.CRYPTO),
    **dict.fromkeys(ETF_SYMBOLS, AssetClass.ETF),
    **dict.fromkeys(STOCK_SYMBOLS, AssetClass.STOCK),
    **dict.fromkeys(FUTURES_SYMBOLS, AssetClass.FUTURES),
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
_YAHOO_FUTURE = re.compile(r"^[A-Z0-9]{1,5}=F$")


def is_tracked(symbol: str) -> bool:
    """Return True if the symbol is on the dashboard watchlist."""
    return symbol.upper() in TRACKED_SYMBOLS_SET


def looks_like_yahoo_future(symbol: str) -> bool:
    """True for a Yahoo continuous futures root such as ``ES=F`` or ``6E=F``.

    Spot crypto (``BTC``) and US equity tickers do not match.
    """
    return bool(_YAHOO_FUTURE.fullmatch(symbol.upper().strip()))


def looks_like_us_equity_ticker(symbol: str) -> bool:
    """True for a 1–5 letter US ticker that is not a tracked crypto symbol.

    Used by Surface 4 / Yahoo so seed names (CRDO, ALAB, …) can fetch OHLCV
    without being added to Surface 1 ``TRACKED_SYMBOLS``.
    ``ES=F`` is a Yahoo future, not an equity ticker.
    """
    normalized = symbol.upper().strip()
    if looks_like_yahoo_future(normalized):
        return False
    if not _US_EQUITY_TICKER.fullmatch(normalized):
        return False
    return normalized not in ASSET_CLASS_MAP or ASSET_CLASS_MAP[normalized] != AssetClass.CRYPTO


def get_asset_class(symbol: str) -> AssetClass:
    """Return the asset class for a tracked or Yahoo-futures symbol."""
    normalized = symbol.upper().strip()
    if normalized in ASSET_CLASS_MAP:
        return ASSET_CLASS_MAP[normalized]
    if looks_like_yahoo_future(normalized):
        return AssetClass.FUTURES
    msg = f"Symbol '{normalized}' is not tracked"
    raise ValueError(msg)


def resolve_asset_class(symbol: str) -> AssetClass | None:
    """Watchlist class, STOCK for an untracked US ticker, or FUTURES for ``=F``."""
    try:
        return get_asset_class(symbol)
    except ValueError:
        if looks_like_us_equity_ticker(symbol):
            return AssetClass.STOCK
        if looks_like_yahoo_future(symbol):
            return AssetClass.FUTURES
        return None


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
