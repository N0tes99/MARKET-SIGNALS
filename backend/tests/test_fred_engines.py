"""FRED macro/event engine tests — endpoint mapping and soft-fail behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.engines.event_engine import engine as event_mod
from app.engines.event_engine.engine import EventEngine, _fetch_fred_macro_events
from app.engines.macro_engine import engine as macro_mod
from app.engines.macro_engine.engine import MacroEngine


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """httpx.Client stand-in that records requests."""

    instances: list[_FakeClient] = []

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        del args, kwargs
        self.calls: list[tuple[str, dict]] = []
        _FakeClient.instances.append(self)

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        del args

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        params = params or {}
        self.calls.append((url, params))
        if "series/observations" in url:
            series_id = params.get("series_id")
            if series_id == "BAD":
                return _FakeResponse(400, {"error_message": "series does not exist"})
            if series_id == "EMPTY":
                return _FakeResponse(200, {"observations": [{"value": "."}]})
            return _FakeResponse(200, {"observations": [{"value": "4.25"}]})

        # release/dates
        assert "/fred/release/dates" in url
        assert "/releases/dates" not in url
        release_id = int(params["release_id"])
        soon = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
        return _FakeResponse(
            200,
            {"release_dates": [{"release_id": release_id, "date": soon}]},
        )


@pytest.fixture(autouse=True)
def _clear_fred_caches() -> None:
    macro_mod._MACRO_CACHE.clear()
    event_mod._FRED_EVENTS_CACHE.clear()
    event_mod._EVENT_CACHE.clear()
    _FakeClient.instances.clear()
    yield
    macro_mod._MACRO_CACHE.clear()
    event_mod._FRED_EVENTS_CACHE.clear()
    event_mod._EVENT_CACHE.clear()
    _FakeClient.instances.clear()


def test_fred_macro_release_ids_and_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_mod.httpx, "Client", _FakeClient)
    events = _fetch_fred_macro_events("fake-key", horizon_days=14)
    labels = {label for label, _ in events}
    assert labels == {"CPI", "Employment Situation", "FOMC Press Release"}

    assert event_mod._FRED_MACRO_RELEASES == (
        ("CPI", 10),
        ("Employment Situation", 50),
        ("FOMC Press Release", 101),
    )

    urls = [url for client in _FakeClient.instances for url, _ in client.calls]
    assert urls
    assert all("/fred/release/dates" in url for url in urls)
    assert all("/fred/releases/dates" not in url for url in urls)

    release_ids = {
        int(params["release_id"])
        for client in _FakeClient.instances
        for _, params in client.calls
    }
    assert release_ids == {10, 50, 101}


def test_event_engine_shared_fred_calendar_across_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(event_mod.httpx, "Client", _FakeClient)
    engine = EventEngine(fred_api_key="fake-key")
    btc = engine.snapshot("BTC")
    eth = engine.snapshot("ETH")
    assert "CPI" in btc.description
    assert btc.description == eth.description
    # Shared FRED calendar fetched once (3 releases), not per symbol.
    assert len(_FakeClient.instances) == 3


def test_macro_one_bad_series_does_not_poison_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "DTWEXBGS": "100.0",
        "DGS10": "BAD",
        "FEDFUNDS": "4.0",
        "UNRATE": "4.1",
    }

    class _PartialClient(_FakeClient):
        def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            params = params or {}
            self.calls.append((url, params))
            series_id = params.get("series_id")
            raw = values.get(str(series_id), "1.0")
            if raw == "BAD":
                return _FakeResponse(400, {"error_message": "bad series"})
            return _FakeResponse(200, {"observations": [{"value": raw}]})

    monkeypatch.setattr(macro_mod.httpx, "Client", _PartialClient)
    snap = MacroEngine(fred_api_key="fake-key").snapshot()
    assert snap.dxy == 100.0
    assert snap.treasury_10y is None
    assert snap.fed_funds_rate == 4.0
    assert snap.unemployment_rate == 4.1
    assert "DXY" in snap.description
    assert "Fed funds" in snap.description


def test_macro_degraded_message_when_key_present_but_all_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailClient(_FakeClient):
        def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            params = params or {}
            self.calls.append((url, params))
            return _FakeResponse(500, {"error_message": "down"})

    monkeypatch.setattr(macro_mod.httpx, "Client", _FailClient)
    snap = MacroEngine(fred_api_key="fake-key").snapshot()
    assert snap.score == 50.0
    assert "degraded" in snap.description.lower()
    assert "add FRED_API_KEY" not in snap.description


def test_macro_missing_key_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(macro_mod.settings, "fred_api_key", "")
    snap = MacroEngine(fred_api_key=None).snapshot()
    assert "FRED_API_KEY" in snap.description
