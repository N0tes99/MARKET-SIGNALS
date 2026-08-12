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
    assert names == ["KrakenProvider"]


def test_binance_opt_in_on_render(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("BINANCE_ENABLED", "true")
    assert use_binance() is True


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
