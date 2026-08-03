"""Indicator unit tests."""


from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_ema
from app.indicators.macd import calculate_macd
from app.indicators.rsi import calculate_rsi
from app.indicators.volume import calculate_volume_ratio
from app.market_data.providers.mock import generate_trending_ohlcv


def test_calculate_ema_returns_same_length() -> None:
    """EMA output aligns with input series length."""
    df = generate_trending_ohlcv(100)
    ema = calculate_ema(df["close"], 20)
    assert len(ema) == len(df)


def test_calculate_rsi_bounded() -> None:
    """RSI values stay within 0–100."""
    df = generate_trending_ohlcv(100)
    rsi = calculate_rsi(df["close"])
    assert rsi.min() >= 0
    assert rsi.max() <= 100


def test_calculate_macd_returns_three_series() -> None:
    """MACD returns line, signal, and histogram."""
    df = generate_trending_ohlcv(100)
    macd, signal, hist = calculate_macd(df["close"])
    assert len(macd) == len(df)
    assert len(signal) == len(df)
    assert len(hist) == len(df)


def test_calculate_atr_positive() -> None:
    """ATR values are non-negative."""
    df = generate_trending_ohlcv(100)
    atr = calculate_atr(df["high"], df["low"], df["close"])
    assert (atr.dropna() >= 0).all()


def test_calculate_volume_ratio() -> None:
    """Volume ratio is computed relative to moving average."""
    df = generate_trending_ohlcv(100)
    ratio = calculate_volume_ratio(df["volume"])
    assert len(ratio) == len(df)
    assert ratio.iloc[-1] > 0
