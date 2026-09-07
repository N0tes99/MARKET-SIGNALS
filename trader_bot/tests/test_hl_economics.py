from __future__ import annotations

import pytest

from hl_scalper.exchange_parse import parse_ioc_fill
from hl_scalper.sim import estimated_round_trip_bps, ioc_limit_px, ioc_slip_frac


def test_ioc_slip_matches_live_floor() -> None:
    assert ioc_slip_frac(2.0, min_slip_bps=5.0) == 0.0005
    assert ioc_slip_frac(12.0, min_slip_bps=5.0) == 0.0012
    assert ioc_limit_px(side="buy", mid=100.0, spread_bps=2.0, min_slip_bps=5.0) == 100.05
    assert ioc_limit_px(side="sell", mid=100.0, spread_bps=2.0, min_slip_bps=5.0) == 99.95


def test_round_trip_bps() -> None:
    rt = estimated_round_trip_bps(
        4.0,
        taker_fee_bps=3.5,
        fee_edge_buffer_bps=2.0,
        min_slip_bps=5.0,
    )
    # entry max(4,5)=5 + exit 5 + fees 7 + buffer 2 = 19
    assert rt == 19.0


def test_parse_ioc_filled() -> None:
    raw = {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {"filled": {"totalSz": "0.01", "avgPx": "100.5"}},
                ]
            },
        },
    }
    parsed = parse_ioc_fill(raw)
    assert parsed["ok"] is True
    assert parsed["filled_sz"] == 0.01
    assert parsed["avg_px"] == pytest.approx(100.5)


def test_parse_ioc_unfilled_error() -> None:
    raw = {
        "status": "ok",
        "response": {"data": {"statuses": [{"error": "Insufficient margin"}]}},
    }
    parsed = parse_ioc_fill(raw)
    assert parsed["ok"] is False
    assert parsed["status"] == "unfilled"
