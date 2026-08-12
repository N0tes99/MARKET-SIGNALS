"""Alpaca read-only mirror client tests (mocked HTTP)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.brokers import alpaca as alpaca_mod
from app.adapters.brokers.alpaca import (
    clear_alpaca_mirror_cache,
    fetch_alpaca_mirror,
)
from app.adapters.brokers.base import ReadOnlyBrokerAdapter


@pytest.fixture(autouse=True)
def _reset_cache_and_keys(monkeypatch):
    clear_alpaca_mirror_cache()
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "")
    monkeypatch.setattr(
        alpaca_mod.settings,
        "alpaca_base_url",
        "https://paper-api.alpaca.markets",
    )
    yield
    clear_alpaca_mirror_cache()


def test_unconfigured_returns_graceful_empty() -> None:
    snap = fetch_alpaca_mirror()
    assert snap.configured is False
    assert snap.mode == "unconfigured"
    assert snap.account is None
    assert snap.positions == []
    assert snap.recent_fills == []
    assert snap.error is None


def test_fetch_mirror_parses_account_positions_fills(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK_TEST")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK_TEST")

    account_payload = {
        "equity": "105000.50",
        "cash": "25000",
        "buying_power": "50000",
        "portfolio_value": "105000.50",
        "status": "ACTIVE",
        "currency": "USD",
    }
    positions_payload = [
        {
            "symbol": "AAPL",
            "qty": "10",
            "side": "long",
            "market_value": "1900",
            "cost_basis": "1800",
            "unrealized_pl": "100",
            "unrealized_plpc": "0.0555",
            "current_price": "190",
            "avg_entry_price": "180",
            "change_today": "0.01",
        },
        {
            "symbol": "MSFT",
            "qty": "5",
            "side": "long",
            "market_value": "2000",
            "cost_basis": "1950",
            "unrealized_pl": "50",
            "unrealized_plpc": "0.0256",
            "current_price": "400",
            "avg_entry_price": "390",
            "change_today": "-0.002",
        },
    ]
    orders_payload = [
        {
            "id": "ord-1",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "filled_qty": "10",
            "filled_avg_price": "180.25",
            "filled_at": "2026-08-10T15:30:00Z",
            "status": "filled",
            "type": "market",
        },
        {
            "id": "ord-skip",
            "symbol": "TSLA",
            "side": "buy",
            "qty": "1",
            "filled_qty": "0",
            "status": "canceled",
            "type": "limit",
        },
    ]

    calls: list[tuple[str, dict | None]] = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

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
            assert self.headers.get("APCA-API-SECRET-KEY") == "SK_TEST"
            if url.endswith("/v2/account"):
                return _Resp(account_payload)
            if url.endswith("/v2/positions"):
                return _Resp(positions_payload)
            if url.endswith("/v2/orders"):
                return _Resp(orders_payload)
            raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(alpaca_mod.httpx, "Client", _Client)

    snap = fetch_alpaca_mirror(use_cache=False)
    assert snap.configured is True
    assert snap.mode == "paper"
    assert snap.error is None
    assert snap.account is not None
    assert snap.account.equity == pytest.approx(105000.50)
    assert snap.account.cash == 25000.0
    assert len(snap.positions) == 2
    # Sorted by abs market value desc — MSFT 2000 before AAPL 1900
    assert snap.positions[0].symbol == "MSFT"
    assert snap.positions[1].symbol == "AAPL"
    assert snap.positions[1].unrealized_pl == 100.0
    assert len(snap.recent_fills) == 1
    assert snap.recent_fills[0].symbol == "AAPL"
    assert snap.recent_fills[0].filled_avg_price == pytest.approx(180.25)
    assert snap.recent_fills[0].filled_at == datetime(2026, 8, 10, 15, 30, tzinfo=UTC)

    assert any(u.endswith("/v2/account") for u, _ in calls)
    assert any(u.endswith("/v2/positions") for u, _ in calls)
    order_calls = [p for u, p in calls if u.endswith("/v2/orders")]
    assert order_calls and order_calls[0]["status"] == "closed"


def test_http_error_returns_configured_with_error(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK_TEST")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK_TEST")

    class _Resp:
        status_code = 401
        text = "unauthorized"

        def raise_for_status(self) -> None:
            raise alpaca_mod.httpx.HTTPStatusError(
                "401",
                request=alpaca_mod.httpx.Request("GET", "https://paper-api.alpaca.markets/v2/account"),
                response=alpaca_mod.httpx.Response(401, text="unauthorized"),
            )

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr(alpaca_mod.httpx, "Client", _Client)
    snap = fetch_alpaca_mirror(use_cache=False)
    assert snap.configured is True
    assert snap.error is not None
    assert "401" in snap.error
    assert snap.positions == []


def test_cache_hit_sets_cached_flag(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK_TEST")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK_TEST")
    hits = {"n": 0}

    class _Resp:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "equity": "1",
                "cash": "1",
                "buying_power": "1",
                "portfolio_value": "1",
                "status": "ACTIVE",
                "currency": "USD",
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
            if url.endswith("/v2/positions") or url.endswith("/v2/orders"):
                return _ListResp()
            return _Resp()

    class _ListResp(_Resp):
        def json(self):
            return []

    monkeypatch.setattr(alpaca_mod.httpx, "Client", _Client)
    first = fetch_alpaca_mirror()
    second = fetch_alpaca_mirror()
    assert first.cached is False
    assert second.cached is True
    assert hits["n"] == 1


def test_live_mode_detection(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "PK")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "SK")
    monkeypatch.setattr(
        alpaca_mod.settings,
        "alpaca_base_url",
        "https://api.alpaca.markets",
    )

    class _Resp:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self):
            if getattr(self, "_list", False):
                return []
            return {
                "equity": "1",
                "cash": "1",
                "buying_power": "1",
                "portfolio_value": "1",
                "status": "ACTIVE",
            }

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, params: dict | None = None):
            r = _Resp()
            if url.endswith("/v2/positions") or url.endswith("/v2/orders"):
                r._list = True  # type: ignore[attr-defined]
            return r

    monkeypatch.setattr(alpaca_mod.httpx, "Client", _Client)
    snap = fetch_alpaca_mirror(use_cache=False)
    assert snap.mode == "live"
    assert snap.base_url == "https://api.alpaca.markets"


def test_adapter_satisfies_readonly_protocol(monkeypatch) -> None:
    """Smoke: module helpers line up with the planned read-only adapter shape."""

    class _Adapter:
        def configured(self) -> bool:
            return alpaca_mod.alpaca_configured()

        def get_mirror(self):
            return fetch_alpaca_mirror(use_cache=False)

    adapter = _Adapter()
    assert isinstance(adapter, ReadOnlyBrokerAdapter)
    assert adapter.configured() is False
