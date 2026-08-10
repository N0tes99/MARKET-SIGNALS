"""Score option candidates for Layer 3 convexity setups."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.engines.opportunity_engine.equity_options.option_chain import RawOptionRow
from app.engines.opportunity_engine.equity_options.types import DirectionBias, OptionCandidate
from app.utils.scoring_helpers import clamp_score


def _mid(bid: float | None, ask: float | None) -> float | None:
    if bid is not None and ask is not None and bid >= 0 and ask >= bid:
        return round((bid + ask) / 2.0, 4)
    if ask is not None and ask > 0:
        return round(ask, 4)
    if bid is not None and bid > 0:
        return round(bid, 4)
    return None


def score_option_candidates(
    symbol: str,
    spot: float,
    direction: DirectionBias,
    rows: list[RawOptionRow],
    *,
    as_of: date | None = None,
    max_candidates: int = 5,
) -> list[OptionCandidate]:
    """Rank OTM options for asymmetric exposure.

    Prefers liquid, moderately OTM contracts with usable DTE over lottery tickets.
    """
    if spot <= 0 or direction not in {"long", "short"}:
        return []

    today = as_of or datetime.now(UTC).date()
    want_right = "call" if direction == "long" else "put"
    scored: list[OptionCandidate] = []

    for row in rows:
        if row.right != want_right:
            continue
        try:
            exp_date = date.fromisoformat(row.expiry)
        except ValueError:
            continue
        dte = (exp_date - today).days
        if dte < 7 or dte > 75:
            continue

        if want_right == "call":
            otm_pct = ((row.strike - spot) / spot) * 100.0
        else:
            otm_pct = ((spot - row.strike) / spot) * 100.0

        if otm_pct < 2.0 or otm_pct > 30.0:
            continue

        mid = _mid(row.bid, row.ask)
        if mid is not None and mid < 0.05:
            continue

        convexity = clamp_score(40 + otm_pct * 1.8 + max(0, 35 - dte) * 0.6)

        vol = row.volume or 0
        oi = row.open_interest or 0
        spread = None
        if row.bid is not None and row.ask is not None and mid and mid > 0:
            spread = (row.ask - row.bid) / mid
        liquidity = 35.0
        liquidity += min(vol, 5000) / 5000 * 25.0
        liquidity += min(oi, 10000) / 10000 * 25.0
        if spread is not None:
            liquidity += clamp_score(20 - spread * 40, -15, 15)
        else:
            liquidity -= 10.0
        liquidity = clamp_score(liquidity)

        if 21 <= dte <= 45:
            theta = 85.0
        elif 14 <= dte < 21:
            theta = 65.0
        elif 45 < dte <= 60:
            theta = 70.0
        else:
            theta = 45.0
        if otm_pct > 22:
            theta -= 18.0
        theta = clamp_score(theta)

        if row.iv is None:
            iv_value = 55.0
        else:
            iv_pct = row.iv * 100.0 if row.iv <= 3 else row.iv
            if iv_pct <= 55:
                iv_value = 78.0
            elif iv_pct <= 80:
                iv_value = 68.0
            elif iv_pct <= 110:
                iv_value = 52.0
            else:
                iv_value = 38.0

        otm_fit = 90.0 - abs(otm_pct - 12.0) * 3.2
        overall = clamp_score(
            convexity * 0.28
            + liquidity * 0.28
            + theta * 0.22
            + iv_value * 0.12
            + clamp_score(otm_fit) * 0.10
        )

        rationale_bits = [
            f"{otm_pct:.0f}% OTM",
            f"{dte}DTE",
            f"liq {liquidity:.0f}",
        ]
        if mid is not None:
            rationale_bits.append(f"mid ${mid:.2f}")
        if otm_pct >= 22:
            rationale_bits.append(
                "lottery convexity — inferior risk-adjusted vs nearer strikes"
            )

        scored.append(
            OptionCandidate(
                underlying=symbol.upper(),
                expiry=row.expiry,
                strike=float(row.strike),
                right=want_right,  # type: ignore[arg-type]
                bid=row.bid,
                ask=row.ask,
                mid=mid,
                volume=row.volume,
                open_interest=row.open_interest,
                iv=row.iv,
                otm_pct=round(otm_pct, 2),
                dte=dte,
                convexity_score=convexity,
                liquidity_score=liquidity,
                theta_score=theta,
                iv_value_score=iv_value,
                overall_score=overall,
                rationale="; ".join(rationale_bits),
            )
        )

    scored.sort(key=lambda c: c.overall_score, reverse=True)
    return scored[:max_candidates]
