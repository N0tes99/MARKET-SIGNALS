"""Alpaca free-tier IEX activity client tests (mocked HTTP)."""

from __future__ import annotations

import pytest

from app.adapters.brokers import alpaca as alpaca_mod
from app.adapters.brokers import alpaca_market_data as amd
from app.adapters.brokers.alpaca_market_data import (
    clear_alpaca_activity_cache,
    fetch_alpaca_activity,
    normalize_activity_symbols,
)


@pytest.fixture(autouse=True)
def _reset_cache_and_keys(monkeypatch):
    clear_alpaca_activity_cache()
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "")
    monkeypatch.setattr(
        amd.settings,
        "alpaca_data_base_url",
        "https://data.alpaca.markets",
    )
    yield
    clear_alpaca_activity_cache()


def test_unconfigured_returns_graceful_empty() -> None:
    snap = fetch_alpaca_activity(["AAPL"])
    assert snap.configured is False
    assert snap.feed == "iex"
    assert snap.rows == []
    assert snap.error is None


def test_normalize_drops_crypto_and_caps() -> None:
    out = normalize_activity_symbols(["AAPL", "btc", "MSFT", "AAPL", "ETH"], limit=10)
    assert out == ["AAPL", "MSFT"]
    assert "BTC" not in out
    assert "ETH" not in out


def test_fetch_snapshots_uses_iex_never_sip(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK_TEST")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK_TEST")

    calls: list[tuple[str, dict | None]] = []

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {
                "AAPL": {
                    "latestTrade": {
                        "p": 190.25,
                        "s": 10,
                        "t": "2026-08-11T15:30:00Z",
                    },
                    "dailyBar": {"o": 188.0, "h": 191.0, "l": 187.0, "c": 190.0, "v": 1_250_000},
                    "prevDailyBar": {
                        "o": 185.0,
                        "h": 189.0,
                        "l": 184.0,
                        "c": 187.0,
                        "v": 900_000,
                    },
                },
                "MSFT": {
                    "latestTrade": {"p": 420.0, "t": "2026-08-11T15:31:00Z"},
                    "dailyBar": {"o": 418.0, "c": 419.5, "v": 800_000},
                    "prevDailyBar": {"c": 415.0, "v": 700_000},
                },
            }

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            self.headers = kwargs.get("headers") or {}

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, params: dict | None = None):
            calls.append((url, params))
            assert self.headers.get("APCA-API-KEY-ID") == "PK_TEST"
            assert url == "https://data.alpaca.markets/v2/stocks/snapshots"
            assert params is not None
            assert params.get("feed") == "iex"
            assert "sip" not in str(params).lower()
            assert params.get("feed") != "sip"
            return _Resp()

    monkeypatch.setattr(amd.httpx, "Client", _Client)

    snap = fetch_alpaca_activity(["AAPL", "MSFT", "BTC"], use_cache=False)
    assert snap.configured is True
    assert snap.feed == "iex"
    assert snap.error is None
    assert snap.symbols_requested == ["AAPL", "MSFT"]
    assert len(snap.rows) == 2
    by_sym = {r.symbol: r for r in snap.rows}
    assert by_sym["AAPL"].last_price == pytest.approx(190.25)
    assert by_sym["AAPL"].daily_volume == pytest.approx(1_250_000)
    # (190.25 - 187) / 187
    assert by_sym["AAPL"].change_pct == pytest.approx((190.25 - 187.0) / 187.0)

    assert len(calls) == 1
    _, params = calls[0]
    assert params["feed"] == "iex"
    assert "sip" not in params.get("symbols", "").lower()
    # Absolute: no SIP feed ever requested
    for _url, p in calls:
        assert p is not None
        assert p.get("feed") == "iex"
        assert p.get("feed") != "sip"
        assert "sip" not in (p.get("feed") or "")


def test_soft_fail_on_403(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK")

    class _Resp:
        status_code = 403
        text = "forbidden"

        def json(self):
            raise AssertionError("should not parse body on soft-fail")

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr(amd.httpx, "Client", _Client)
    snap = fetch_alpaca_activity(["AAPL"], use_cache=False)
    assert snap.configured is True
    assert snap.rows == []
    assert snap.error is not None
    assert "403" in snap.error


def test_soft_fail_on_429(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK")

    class _Resp:
        status_code = 429
        text = "rate limited"

        def json(self):
            return {}

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr(amd.httpx, "Client", _Client)
    snap = fetch_alpaca_activity(["AAPL"], use_cache=False)
    assert snap.configured is True
    assert snap.rows == []
    assert "429" in (snap.error or "")


def test_activity_cache_hit(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK")
    hits = {"n": 0}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {
                "AAPL": {
                    "latestTrade": {"p": 1.0},
                    "dailyBar": {"c": 1.0, "v": 100},
                    "prevDailyBar": {"c": 1.0},
                }
            }

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            hits["n"] += 1
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, params: dict | None = None):
            assert params is not None and params.get("feed") == "iex"
            return _Resp()

    monkeypatch.setattr(amd.httpx, "Client", _Client)
    first = fetch_alpaca_activity(["AAPL"])
    second = fetch_alpaca_activity(["AAPL"])
    assert first.cached is False
    assert second.cached is True
    assert hits["n"] == 1
