"""Put/call and unusual-volume proxies from a Yahoo option chain."""

from __future__ import annotations

from app.engines.opportunity_engine.equity_options.option_chain import RawOptionRow
from app.engines.options_tape.types import OptionFlow
from app.utils.scoring_helpers import clamp_score


def _vol_oi(volume: int, open_interest: int) -> float:
    if open_interest <= 0:
        return float(volume) if volume > 0 else 0.0
    return volume / open_interest


def score_option_flow(rows: list[RawOptionRow]) -> OptionFlow:
    """Aggregate chain activity. Paid flow feeds are not used."""
    call_vol = 0
    put_vol = 0
    call_oi = 0
    put_oi = 0
    max_call = 0.0
    max_put = 0.0

    for row in rows:
        vol = int(row.volume or 0)
        oi = int(row.open_interest or 0)
        ratio = _vol_oi(vol, oi)
        if row.right == "call":
            call_vol += vol
            call_oi += oi
            max_call = max(max_call, ratio)
        elif row.right == "put":
            put_vol += vol
            put_oi += oi
            max_put = max(max_put, ratio)

    total = call_vol + put_vol
    pc_vol = put_vol / call_vol if call_vol > 0 else (99.0 if put_vol > 0 else 1.0)
    pc_oi = put_oi / call_oi if call_oi > 0 else (99.0 if put_oi > 0 else 1.0)

    long_flow = 50.0
    long_flow += clamp_score((1.0 - pc_vol) * 18.0, -16, 16)
    long_flow += clamp_score(max_call * 12.0, 0, 16)
    if total >= 25_000:
        long_flow += 4.0

    short_flow = 50.0
    short_flow += clamp_score((pc_vol - 1.0) * 18.0, -16, 16)
    short_flow += clamp_score(max_put * 12.0, 0, 16)
    if total >= 25_000:
        short_flow += 4.0

    factors: list[str] = []
    conflicts: list[str] = []
    if total <= 0:
        conflicts.append("No option volume on the fetched chain")
    else:
        factors.append(f"Chain volume {total:,.0f} · P/C {pc_vol:.2f}")
    if max_call >= 0.8:
        factors.append(f"Call vol/OI {max_call:.1f}×")
    if max_put >= 0.8:
        factors.append(f"Put vol/OI {max_put:.1f}×")
    if pc_vol >= 1.4:
        factors.append("Put volume leading")
    elif pc_vol <= 0.7:
        factors.append("Call volume leading")

    return OptionFlow(
        call_volume=call_vol,
        put_volume=put_vol,
        call_oi=call_oi,
        put_oi=put_oi,
        put_call_vol=round(pc_vol, 3),
        put_call_oi=round(pc_oi, 3),
        max_call_vol_oi=round(max_call, 3),
        max_put_vol_oi=round(max_put, 3),
        total_option_volume=total,
        long_flow=clamp_score(long_flow),
        short_flow=clamp_score(short_flow),
        factors=factors,
        conflicts=conflicts,
    )
