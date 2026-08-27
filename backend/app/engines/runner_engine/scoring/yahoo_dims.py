"""Radar dimensions from a Yahoo snapshot — score only fields that exist."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.engines.runner_engine.scoring.edgar import EdgarSnapshot
from app.engines.runner_engine.scoring.yahoo_snapshot import YahooRunnerSnapshot
from app.engines.runner_engine.types import DimensionScore
from app.utils.scoring_helpers import clamp_score

_BOTTLENECKS: tuple[tuple[str, float, str], ...] = (
    ("semiconductor", 82.0, "semiconductor / packaging"),
    ("electrical equipment", 78.0, "electrical equipment / grid"),
    ("independent power", 76.0, "independent power"),
    ("uranium", 84.0, "uranium fuel"),
    ("copper", 74.0, "copper supply"),
    ("electronic component", 76.0, "electronic components"),
    ("communication equipment", 72.0, "optical / comms hardware"),
    ("computer hardware", 70.0, "compute hardware"),
    ("metal fabrication", 72.0, "precision metals"),
    ("software—infrastructure", 66.0, "infra software"),
    ("software - infrastructure", 66.0, "infra software"),
)


def _missing(name: str, reason: str) -> DimensionScore:
    """Quiet miss — dash in UI, no conflict spam."""
    return DimensionScore(
        name=name,
        score=50.0,
        confidence=0.2,
        factors=[reason],
        conflicts=[],
        data_quality="missing",
    )


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def qoq_acceleration(
    revenues: tuple[float, ...],
) -> tuple[float | None, float | None]:
    """Newest-first revenues → (latest QoQ growth, QoQ acceleration)."""
    if len(revenues) < 3:
        return None, None
    rates: list[float] = []
    for index in range(len(revenues) - 1):
        prior = revenues[index + 1]
        if abs(prior) < 1.0:
            return None, None
        rates.append((revenues[index] - prior) / abs(prior))
        if len(rates) == 2:
            break
    if len(rates) < 2:
        return None, None
    return rates[0], rates[0] - rates[1]


def _pp(value: float) -> str:
    return f"{value * 100:+.1f}pp"


def score_fundamental(snap: YahooRunnerSnapshot) -> DimensionScore:
    """Revenue/EPS acceleration + margins from Yahoo. No 50-fill when empty."""
    latest_qoq, accel = qoq_acceleration(snap.quarterly_revenue)
    fields = [
        snap.revenue_growth,
        snap.earnings_quarterly_growth or snap.earnings_growth,
        snap.profit_margins,
        snap.return_on_equity,
        snap.trailing_pe,
        snap.forward_pe,
        latest_qoq,
    ]
    present = sum(1 for item in fields if item is not None)
    if present == 0:
        return _missing("fundamental", "Yahoo had no growth/margin/PE fields")

    score = 50.0
    factors: list[str] = []
    conflicts: list[str] = []

    if snap.revenue_growth is not None:
        score += clamp_score(snap.revenue_growth * 40.0, -16, 18)
        factors.append(f"Revenue growth {_pct(snap.revenue_growth)}")
        if snap.revenue_growth < -0.05:
            conflicts.append("Revenue contracting")

    if latest_qoq is not None:
        score += clamp_score(latest_qoq * 20.0, -10, 12)
        factors.append(f"QoQ revenue {_pct(latest_qoq)}")
    if accel is not None:
        score += clamp_score(accel * 40.0, -12, 14)
        factors.append(f"QoQ acceleration {_pp(accel)}")
        if accel < -0.08:
            conflicts.append("Revenue growth decelerating")
        elif accel >= 0.05:
            factors.append("Growth accelerating")

    earn = snap.earnings_quarterly_growth
    if earn is None:
        earn = snap.earnings_growth
    if earn is not None:
        score += clamp_score(earn * 28.0, -14, 16)
        factors.append(f"Earnings growth {_pct(earn)}")
        if earn < -0.10:
            conflicts.append("Earnings contracting")

    if snap.profit_margins is not None:
        if snap.profit_margins >= 0.20:
            score += 10.0
        elif snap.profit_margins >= 0.08:
            score += 6.0
        elif snap.profit_margins < 0:
            score -= 12.0
            conflicts.append("Negative profit margin")
        factors.append(f"Profit margin {_pct(snap.profit_margins)}")

    if snap.return_on_equity is not None:
        if snap.return_on_equity >= 0.18:
            score += 6.0
        elif snap.return_on_equity < 0:
            score -= 8.0
        factors.append(f"ROE {_pct(snap.return_on_equity)}")

    if (
        snap.trailing_pe is not None
        and snap.forward_pe is not None
        and snap.trailing_pe > 0
        and snap.forward_pe > 0
        and snap.forward_pe < snap.trailing_pe * 0.92
    ):
        score += 7.0
        factors.append(
            f"Forward P/E {snap.forward_pe:.1f} below trailing {snap.trailing_pe:.1f}"
        )

    quality = "good" if present >= 2 or accel is not None else "degraded"
    return DimensionScore(
        name="fundamental",
        score=clamp_score(score),
        confidence=0.55 + min(present, 5) * 0.07,
        factors=factors,
        conflicts=conflicts,
        data_quality=quality,
    )


def score_catalyst(
    snap: YahooRunnerSnapshot,
    *,
    today: date | None = None,
    edgar: EdgarSnapshot | None = None,
) -> DimensionScore:
    """Yahoo earnings date, EPS surprise, plus optional EDGAR 8-K overlay."""
    now = today or datetime.now(UTC).date()
    factors: list[str] = []
    conflicts: list[str] = []
    score = 50.0
    quality = "missing"

    if snap.earnings_date is not None:
        days = (snap.earnings_date - now).days
        quality = "good"
        factors.append(f"Earnings {snap.earnings_date.isoformat()} ({days:+d}d)")
        if 0 <= days <= 7:
            score = 82.0
            factors.append("Print inside 7 days")
        elif 8 <= days <= 21:
            score = 74.0
            factors.append("Print inside 21 days")
        elif 22 <= days <= 45:
            score = 64.0
        elif 46 <= days <= 90:
            score = 56.0
        elif -7 <= days < 0:
            score = 68.0
            factors.append("Just reported — reaction window")
        elif days < -7:
            score = 48.0
            factors.append("Last print already aged")
        else:
            score = 52.0
        if 0 <= days <= 5:
            conflicts.append("Near-term earnings — gap risk")

    if edgar is not None and edgar.eight_k_count > 0:
        quality = "good"
        label = edgar.latest_form or "8-K"
        when = edgar.latest_date.isoformat() if edgar.latest_date else "recent"
        factors.append(f"EDGAR {label} x{edgar.eight_k_count} (latest {when})")
        score = clamp_score(score + min(12.0, 6.0 + edgar.eight_k_count * 2.0))
        if edgar.latest_date is not None and (now - edgar.latest_date).days <= 3:
            conflicts.append("Fresh 8-K — event risk")

    surprise = snap.eps_surprise_pct
    surprise_when = snap.eps_surprise_date
    if surprise is not None and surprise_when is not None:
        age = (now - surprise_when).days
        if 0 <= age <= 120:
            quality = "good"
            factors.append(
                f"EPS surprise {surprise:+.1f}% ({surprise_when.isoformat()})"
            )
            if surprise >= 20:
                score = clamp_score(score + 12.0)
            elif surprise >= 5:
                score = clamp_score(score + 8.0)
            elif surprise >= 0:
                score = clamp_score(score + 4.0)
            elif surprise > -8:
                score = clamp_score(score - 6.0)
                conflicts.append("EPS miss vs estimate")
            else:
                score = clamp_score(score - 12.0)
                conflicts.append("Large EPS miss vs estimate")
            if snap.eps_beat_streak >= 3:
                factors.append(f"{snap.eps_beat_streak}-quarter beat streak")
                score = clamp_score(score + 4.0)

    if quality == "missing":
        return _missing(
            "catalyst",
            "Yahoo had no earnings date, surprise, or EDGAR 8-K",
        )

    return DimensionScore(
        name="catalyst",
        score=clamp_score(score),
        confidence=(
            0.7
            if snap.earnings_date is not None
            else 0.68
            if snap.eps_surprise_pct is not None
            else 0.55
        ),
        factors=factors,
        conflicts=conflicts,
        data_quality=quality,
    )


def score_discovery_gap(snap: YahooRunnerSnapshot) -> DimensionScore:
    """Followership vs whether growth/catalyst already sits in the multiple."""
    analysts = snap.number_of_analysts
    cap = snap.market_cap
    growth = snap.revenue_growth
    if growth is None:
        growth = snap.earnings_quarterly_growth or snap.earnings_growth
    _, accel = qoq_acceleration(snap.quarterly_revenue)
    pe: float | None = None
    if snap.forward_pe is not None and snap.forward_pe > 0:
        pe = snap.forward_pe
    elif snap.trailing_pe is not None and snap.trailing_pe > 0:
        pe = snap.trailing_pe
    ps = snap.price_to_sales if snap.price_to_sales and snap.price_to_sales > 0 else None
    has_follow = analysts is not None or cap is not None
    has_value = (pe is not None or ps is not None) and (
        growth is not None or accel is not None
    )
    if not has_follow and not has_value:
        return _missing(
            "discovery_gap",
            "Yahoo had no analyst/cap and no growth-vs-valuation pair",
        )

    score = 50.0
    factors: list[str] = []
    conflicts: list[str] = []

    if analysts is not None:
        if analysts <= 2:
            score = 84.0
        elif analysts <= 5:
            score = 74.0
        elif analysts <= 10:
            score = 62.0
        elif analysts <= 18:
            score = 48.0
        else:
            score = 34.0
        factors.append(f"{analysts} analyst opinions")

    if cap is not None:
        billions = cap / 1_000_000_000.0
        factors.append(f"Market cap ${billions:.2f}B")
        if billions < 2 and (analysts is None or analysts <= 8):
            score += 8.0
        elif billions > 80:
            score -= 14.0
            factors.append("Mega-cap — discovery already done")

    if growth is not None and pe is not None and growth > 0.02:
        peg = pe / (growth * 100.0)
        factors.append(f"PEG {peg:.2f} (P/E {pe:.1f} / growth {_pct(growth)})")
        if peg < 0.8:
            score += 14.0
            factors.append("Growth ahead of valuation")
        elif peg < 1.3:
            score += 7.0
        elif peg > 3.0:
            score -= 16.0
            conflicts.append("Valuation already expanded vs growth")
        elif peg > 2.0:
            score -= 10.0
            factors.append("Price has discounted a lot of the growth")
    elif growth is not None and pe is None and ps is not None:
        factors.append(f"P/S {ps:.1f} with growth {_pct(growth)}")
        if ps < 6 and growth >= 0.20:
            score += 8.0
            factors.append("Sales multiple still quiet vs growth")
        elif ps > 25:
            score -= 10.0
            conflicts.append("Sales multiple already rich")

    if accel is not None:
        factors.append(f"QoQ acceleration {_pp(accel)}")
        if accel >= 0.05:
            score += 10.0
        elif accel <= -0.08:
            score -= 10.0
            conflicts.append("Deceleration — discovery may be a trap")

    if snap.week52_change is not None:
        factors.append(f"52-week change {_pct(snap.week52_change)}")
        if snap.week52_change >= 1.0:
            score -= 12.0
            factors.append("Price already expanded")
        elif snap.week52_change >= 0.50:
            score -= 6.0
        elif snap.week52_change < 0.15 and (growth or 0) >= 0.20:
            score += 8.0
            factors.append("Price has not followed growth")

    quality = "good" if (analysts is not None or has_value) else "degraded"
    return DimensionScore(
        name="discovery_gap",
        score=clamp_score(score),
        confidence=0.62 if analysts is not None else (0.52 if has_value else 0.45),
        factors=factors,
        conflicts=conflicts,
        data_quality=quality,
    )


def score_theme_bottleneck(snap: YahooRunnerSnapshot) -> DimensionScore:
    """Mapped bottleneck industries only — general Tech is not a bottleneck."""
    if not snap.industry and not snap.sector:
        return _missing("theme_bottleneck", "Yahoo had no sector/industry")

    blob = f"{snap.industry or ''} {snap.sector or ''}".lower()
    factors = [f"{snap.sector or '—'} / {snap.industry or '—'}"]
    for needle, hint, label in _BOTTLENECKS:
        if needle in blob:
            return DimensionScore(
                name="theme_bottleneck",
                score=hint,
                confidence=0.6,
                factors=[*factors, f"Mapped bottleneck: {label}"],
                conflicts=[],
                data_quality="good",
            )

    return DimensionScore(
        name="theme_bottleneck",
        score=48.0,
        confidence=0.45,
        factors=[*factors, "No mapped supply-bottleneck theme"],
        conflicts=[],
        data_quality="good",
    )


def score_institutional(snap: YahooRunnerSnapshot) -> DimensionScore:
    """Ownership snapshot — not 13F flow. Label stays honest."""
    inst = snap.held_percent_institutions
    insider = snap.held_percent_insiders
    if inst is None and insider is None:
        return _missing("institutional_accum", "Yahoo had no institutional/insider ownership")

    score = 50.0
    factors: list[str] = ["Ownership snapshot (not 13F change)"]
    if inst is not None:
        factors.append(f"Institutions {_pct(inst)}")
        if 0.35 <= inst <= 0.78:
            score += 12.0
        elif inst > 0.90:
            score -= 8.0
            factors.append("Very high institutional ownership — crowded")
        elif inst < 0.12:
            score -= 4.0
            factors.append("Low institutional sponsorship")

    if insider is not None:
        factors.append(f"Insiders {_pct(insider)}")
        if insider >= 0.10 and inst is not None and 0.25 <= inst <= 0.75:
            score += 6.0

    return DimensionScore(
        name="institutional_accum",
        score=clamp_score(score),
        confidence=0.5,
        factors=factors,
        conflicts=[],
        data_quality="good",
    )


def score_short_squeeze(snap: YahooRunnerSnapshot) -> DimensionScore:
    """Short % of float + days-to-cover. Accelerant only, never a thesis."""
    si = snap.short_percent_of_float
    dtc = snap.short_ratio
    if si is None and dtc is None:
        return _missing("short_squeeze_potential", "Yahoo had no short-interest fields")

    score = 42.0
    factors: list[str] = ["Accelerant only — not a standalone thesis"]
    conflicts: list[str] = []
    if si is not None:
        factors.append(f"Short interest {_pct(si)} of float")
        if si >= 0.30:
            score = 80.0
            conflicts.append("Very high SI — squeeze or unwind risk")
        elif si >= 0.20:
            score = 72.0
        elif si >= 0.10:
            score = 60.0
        elif si >= 0.05:
            score = 50.0
        else:
            score = 38.0

    if dtc is not None:
        factors.append(f"Days to cover {dtc:.1f}")
        if dtc >= 10:
            score += 10.0
        elif dtc >= 5:
            score += 6.0

    if (
        snap.shares_short is not None
        and snap.shares_short_prior is not None
        and snap.shares_short_prior > 0
    ):
        change = (snap.shares_short - snap.shares_short_prior) / snap.shares_short_prior
        factors.append(f"SI vs prior month {change:+.0%}")
        if change >= 0.10:
            score += 6.0
        elif change <= -0.15:
            score -= 4.0

    return DimensionScore(
        name="short_squeeze_potential",
        score=clamp_score(score),
        confidence=0.58,
        factors=factors,
        conflicts=conflicts,
        data_quality="good",
    )
