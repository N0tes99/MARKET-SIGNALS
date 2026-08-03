"""Tracked symbol registry tests."""

from app.market_data.symbols import (
    ASSET_CLASS_MAP,
    BINANCE_SYMBOL_MAP,
    CRYPTO_SYMBOLS,
    ETF_SYMBOLS,
    KRAKEN_PAIR_MAP,
    STOCK_SYMBOLS,
    TRACKED_SYMBOLS,
    AssetClass,
    get_asset_class,
    is_crypto,
    is_tracked,
    to_kraken_pair,
)


def test_tracked_symbols_count() -> None:
    assert len(TRACKED_SYMBOLS) == 60
    assert len(CRYPTO_SYMBOLS) == 25
    assert len(ETF_SYMBOLS) == 12
    assert len(STOCK_SYMBOLS) == 23


def test_crypto_symbols_have_exchange_mappings() -> None:
    for symbol in CRYPTO_SYMBOLS:
        assert symbol in BINANCE_SYMBOL_MAP
        assert symbol in KRAKEN_PAIR_MAP
        assert is_tracked(symbol)
        assert is_crypto(symbol)
        assert get_asset_class(symbol) == AssetClass.CRYPTO


def test_equity_symbols_have_asset_class() -> None:
    for symbol in ETF_SYMBOLS:
        assert get_asset_class(symbol) == AssetClass.ETF
        assert symbol not in BINANCE_SYMBOL_MAP
    for symbol in STOCK_SYMBOLS:
        assert get_asset_class(symbol) == AssetClass.STOCK
        assert symbol not in BINANCE_SYMBOL_MAP


def test_all_tracked_symbols_mapped() -> None:
    assert set(ASSET_CLASS_MAP) == set(TRACKED_SYMBOLS)


def test_kraken_doge_pair() -> None:
    assert to_kraken_pair("DOGE") == "XDGUSD"
