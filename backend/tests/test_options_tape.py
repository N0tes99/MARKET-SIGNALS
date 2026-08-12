"""Aggressive options tape — symmetric longs/shorts, volume standouts."""

from datetime import UTC, datetime

import pandas as pd
import pytest
from httpx import AsyncClient

from app.core.service_dependencies import get_options_tape_scanner
from app.engines.opportunity_engine.equity_options.option_chain import RawOptionRow
from app.engines.options_tape.engine import _BOARD_CACHE, OptionsTapeScanner
from app.engines.options_tape.flow import score_option_flow
from app.engines.options_tape.screen import score_tape
from app.engines.options_tape.universe import default_tape_universe, merge_extra_symbols
from app.main import app


def _bars(
    *,
    start: float,
    end: float,
    last_vol: float,
    avg_vol: float = 5_000_000,
    bars: int = 60,
) -> pd.DataFrame:
    rows = []
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i in range(bars):
        t = i / max(bars - 1, 1)
        price = start + (end - start) * t
        vol = last_vol if i == bars - 1 else avg_vol
        rows.append(
            {
                "timestamp": base + pd.Timedelta(days=i),
                "open": price - 0.3,
                "high": price + 1.2,
                "low": price - 1.1,
                "close": price,
                "volume": float(vol),
            }
        )
    return pd.DataFrame(rows)


def _chain(spot: float, *, call_vol: int, put_vol: int) -> list[RawOptionRow]:
    return [
        RawOptionRow(
            expiry="2026-09-18",
            strike=round(spot * 1.08, 2),
            right="call",
            bid=1.4,
            ask=1.6,
            volume=call_vol,
            open_interest=4000,
            iv=0.55,
        ),
        RawOptionRow(
            expiry="2026-09-18",
            strike=round(spot * 0.92, 2),
            right="put",
            bid=1.3,
            ask=1.5,
            volume=put_vol,
            open_interest=3500,
            iv=0.58,
        ),
    ]


class _MD:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def safe_get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 90):
        return self.frames.get(symbol.upper())


def test_universe_includes_untracked_and_extras() -> None:
    uni = default_tape_universe()
    assert "NVDA" in uni
    assert "CRDO" in uni
    assert "MARA" in uni
    assert "BTC" not in uni
    merged = merge_extra_symbols(uni, ["zzzz", "btc", "CRDO"])
    assert "ZZZZ" in merged
    assert "BTC" not in merged


def test_volume_spike_up_tape_is_long() -> None:
    frame = _bars(start=80, end=100, last_vol=14_000_000)
    screen = score_tape("HOOD", frame)
    assert screen is not None
    assert screen.standout
    assert screen.relative_volume >= 2.0
    assert screen.long_score > screen.short_score


def test_volume_spike_down_tape_is_short() -> None:
    frame = _bars(start=100, end=78, last_vol=16_000_000)
    screen = score_tape("SMCI", frame)
    assert screen is not None
    assert screen.standout
    assert screen.short_score > screen.long_score


def test_quiet_tape_is_not_a_standout() -> None:
    frame = _bars(start=90, end=91, last_vol=5_100_000, avg_vol=5_000_000)
    screen = score_tape("AAPL", frame)
    assert screen is not None
    assert screen.relative_volume < 1.15
    assert screen.standout is False


def test_put_heavy_flow_favors_shorts() -> None:
    flow = score_option_flow(_chain(100.0, call_vol=800, put_vol=4200))
    assert flow.put_call_vol > 1.4
    assert flow.short_flow > flow.long_flow


def test_board_balances_longs_and_shorts() -> None:
    _BOARD_CACHE.clear()
    md = _MD(
        {
            "BULLA": _bars(start=70, end=95, last_vol=18_000_000),
            "BEARA": _bars(start=110, end=82, last_vol=17_000_000),
            "BULLB": _bars(start=40, end=55, last_vol=12_000_000),
            "BEARB": _bars(start=60, end=44, last_vol=13_000_000),
        }
    )

    def _fetch(symbol: str) -> list[RawOptionRow]:
        last = float(md.frames[symbol]["close"].iloc[-1])
        if symbol.startswith("BULL"):
            return _chain(last, call_vol=5000, put_vol=1200)
        return _chain(last, call_vol=900, put_vol=4800)

    scanner = OptionsTapeScanner(md, chain_fetcher=_fetch)  # type: ignore[arg-type]
    board = scanner.scan_board(extra_symbols=list(md.frames), per_side=2, min_rel_vol=1.2)
    assert len(board.longs) == 2
    assert len(board.shorts) == 2
    assert {h.direction for h in board.longs} == {"long"}
    assert {h.direction for h in board.shorts} == {"short"}
    assert all(h.selected_option is not None for h in (*board.longs, *board.shorts))
    assert all(h.selected_option.right == "call" for h in board.longs)
    assert all(h.selected_option.right == "put" for h in board.shorts)
    assert all(h.relative_volume >= 1.2 for h in (*board.longs, *board.shorts))


@pytest.mark.asyncio
async def test_options_tape_api(client: AsyncClient) -> None:
    _BOARD_CACHE.clear()
    md = _MD(
        {
            "BULLX": _bars(start=50, end=72, last_vol=20_000_000),
            "BEARX": _bars(start=90, end=61, last_vol=19_000_000),
        }
    )

    def _fetch(symbol: str) -> list[RawOptionRow]:
        last = float(md.frames[symbol]["close"].iloc[-1])
        if symbol == "BULLX":
            return _chain(last, call_vol=6000, put_vol=1000)
        return _chain(last, call_vol=700, put_vol=5100)

    scanner = OptionsTapeScanner(md, chain_fetcher=_fetch)  # type: ignore[arg-type]
    app.dependency_overrides[get_options_tape_scanner] = lambda: scanner
    try:
        res = await client.get("/api/v1/options-tape?per_side=1&add=BULLX,BEARX")
        assert res.status_code == 200
        body = res.json()
        assert body["per_side"] == 1
        assert len(body["longs"]) == 1
        assert len(body["shorts"]) == 1
        assert body["longs"][0]["direction"] == "long"
        assert body["shorts"][0]["direction"] == "short"
        assert body["longs"][0]["selected_option"]["right"] == "call"
        assert body["shorts"][0]["selected_option"]["right"] == "put"
        assert "volume" in body["note"].lower() or "tape" in body["note"].lower()
    finally:
        app.dependency_overrides.pop(get_options_tape_scanner, None)
