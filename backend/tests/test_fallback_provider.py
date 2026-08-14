"""Fallback must not traceback-spam on Binance geo-blocks."""

from types import SimpleNamespace

import pytest

from app.market_data.providers.binance import BinanceBlockedError, use_binance
from app.market_data.providers.fallback import FallbackProvider
from app.market_data.service import build_default_provider
from app.market_data.types import DerivativesSnapshot


class _EmptyDeriv:
    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        return DerivativesSnapshot(
            symbol=symbol,
            funding_rate=None,
            open_interest=None,
            mark_price=None,
        )


class _BlockedBinance:
    calls = 0

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        type(self).calls += 1
        raise BinanceBlockedError("Binance HTTP 451")


def test_derivatives_skip_binance_after_451(caplog: pytest.LogCaptureFixture) -> None:
    _BlockedBinance.calls = 0
    chain = FallbackProvider([_EmptyDeriv(), _BlockedBinance()])
    first = chain.get_derivatives("BTC")
    second = chain.get_derivatives("ETH")
    assert first.funding_rate is None
    assert second.funding_rate is None
    assert _BlockedBinance.calls == 1
    assert "geo-blocked" in caplog.text
    assert "Traceback" not in caplog.text


def test_render_skips_binance(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("BINANCE_ENABLED", raising=False)
    assert use_binance() is False
    crypto = build_default_provider()._crypto
    names = [type(p).__name__ for p in crypto._providers]
    assert names == ["KrakenProvider", "DepthDerivativesProvider"]


def test_binance_opt_in_on_render(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("BINANCE_ENABLED", "true")
    assert use_binance() is True
    crypto = build_default_provider()._crypto
    names = [type(p).__name__ for p in crypto._providers]
    assert "BinanceProvider" in names
    assert names[-1] == "DepthDerivativesProvider"


def test_depth_skips_binance_http_on_render(monkeypatch) -> None:
    from app.market_data.providers.bybit_derivatives import (
        _DEPTH_CACHE,
        DerivativesDepth,
        fetch_derivatives_depth,
    )

    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("BINANCE_ENABLED", raising=False)
    calls = {"binance": 0, "bybit": 0}

    def fake_binance(symbol, timeout=2.0):
        calls["binance"] += 1
        return None

    def fake_bybit(symbol, timeout=2.0):
        calls["bybit"] += 1
        return DerivativesDepth(symbol=symbol, funding_rate=0.01, source="bybit")

    monkeypatch.setattr(
        "app.market_data.providers.bybit_derivatives.fetch_binance_depth",
        fake_binance,
    )
    monkeypatch.setattr(
        "app.market_data.providers.bybit_derivatives.fetch_bybit_depth",
        fake_bybit,
    )
    _DEPTH_CACHE._entries.clear()
    out = fetch_derivatives_depth("ZZZGATE")
    assert out is not None
    assert out.source == "bybit"
    assert calls["binance"] == 0
    assert calls["bybit"] == 1


def test_depth_falls_back_to_okx_when_bybit_blocked(monkeypatch) -> None:
    from app.market_data.providers.bybit_derivatives import (
        _DEPTH_CACHE,
        DerivativesDepth,
        fetch_derivatives_depth,
    )

    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("BINANCE_ENABLED", raising=False)
    calls = {"bybit": 0, "okx": 0}

    def fake_bybit(symbol, timeout=2.0):
        calls["bybit"] += 1
        return None

    def fake_okx(symbol, timeout=3.0):
        calls["okx"] += 1
        return DerivativesDepth(symbol=symbol, funding_rate=0.0002, source="okx")

    monkeypatch.setattr(
        "app.market_data.providers.bybit_derivatives.fetch_binance_depth",
        lambda symbol, timeout=2.0: None,
    )
    monkeypatch.setattr(
        "app.market_data.providers.bybit_derivatives.fetch_bybit_depth",
        fake_bybit,
    )
    monkeypatch.setattr(
        "app.market_data.providers.bybit_derivatives.fetch_okx_depth",
        fake_okx,
    )
    _DEPTH_CACHE._entries.clear()
    out = fetch_derivatives_depth("BTC")
    assert out is not None
    assert out.source == "okx"
    assert out.funding_rate == pytest.approx(0.0002)
    assert calls["bybit"] == 1
    assert calls["okx"] == 1


def test_depth_derivatives_provider_fills_kraken_blank(monkeypatch) -> None:
    from app.market_data.providers.bybit_derivatives import DerivativesDepth
    from app.market_data.providers.depth_derivatives import DepthDerivativesProvider
    from app.market_data.providers.kraken import KrakenProvider

    monkeypatch.setattr(
        "app.market_data.providers.depth_derivatives.fetch_derivatives_depth",
        lambda symbol: DerivativesDepth(
            symbol=symbol,
            funding_rate=0.0003,
            open_interest=1_000.0,
            mark_price=50.0,
            source="okx",
        ),
    )
    chain = FallbackProvider([KrakenProvider(timeout=1.0), DepthDerivativesProvider()])
    snap = chain.get_derivatives("SOL")
    assert snap.funding_rate == pytest.approx(0.0003)
    assert snap.open_interest == pytest.approx(1_000.0)
    assert snap.mark_price == pytest.approx(50.0)


def test_derivatives_uses_first_populated() -> None:
    populated = SimpleNamespace(
        get_derivatives=lambda symbol: DerivativesSnapshot(
            symbol=symbol,
            funding_rate=0.01,
            open_interest=12.0,
            mark_price=65000.0,
        )
    )
    chain = FallbackProvider([populated])  # type: ignore[list-item]
    snap = chain.get_derivatives("BTC")
    assert snap.funding_rate == 0.01
