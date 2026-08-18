"""Paper CME futures — Yahoo scanner rows into paper ideas (not crypto perps)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engines.paper_agent.types import PaperDirection
from app.engines.runner_engine.cme_futures import CmeFuturesRow, scan_cme_futures
from app.market_data.service import MarketDataService

SETUP_TYPE = "cme_momentum"
SOURCE = "cme_futures"
MIN_CONFIDENCE = 55.0
TRADEABLE_BUCKETS = frozenset({"trending", "extended"})


@dataclass(frozen=True)
class CmeMomentumIdea:
    """One paper CME candidate from the Yahoo futures scanner."""

    symbol: str
    direction: PaperDirection
    setup_type: str
    confidence: float
    factors: list[str]
    extras: dict[str, Any]


def direction_from_row(row: CmeFuturesRow) -> PaperDirection | None:
    """12h momentum, then session change. Flat or missing → skip."""
    mom = row.mom_12h_pct if row.mom_12h_pct is not None else row.change_pct
    if mom is None:
        return None
    if mom > 0:
        return "long"
    if mom < 0:
        return "short"
    return None


def idea_from_row(
    row: CmeFuturesRow,
    *,
    min_confidence: float = MIN_CONFIDENCE,
) -> CmeMomentumIdea | None:
    """None when quiet, unpriced, or below the paper floor."""
    if row.last is None or row.last <= 0:
        return None
    if row.bucket not in TRADEABLE_BUCKETS:
        return None
    if float(row.score) < min_confidence:
        return None
    direction = direction_from_row(row)
    if direction is None:
        return None
    extras: dict[str, Any] = {
        "group": row.group,
        "bucket": row.bucket,
        "score": row.score,
        "mom_12h_pct": row.mom_12h_pct,
        "change_pct": row.change_pct,
        "oi": row.open_interest,
    }
    factors = [f"{row.group} {row.bucket}", *list(row.factors[:4])]
    return CmeMomentumIdea(
        symbol=row.symbol.upper(),
        direction=direction,
        setup_type=SETUP_TYPE,
        confidence=float(row.score),
        factors=factors[:5],
        extras=extras,
    )


def scan_cme_paper_ideas(
    market: MarketDataService,
    *,
    min_confidence: float = MIN_CONFIDENCE,
) -> list[CmeMomentumIdea]:
    """Scan Yahoo CME names; highest score first."""
    rows = scan_cme_futures(market)
    ideas: list[CmeMomentumIdea] = []
    for row in rows:
        idea = idea_from_row(row, min_confidence=min_confidence)
        if idea is not None:
            ideas.append(idea)
    ideas.sort(key=lambda i: i.confidence, reverse=True)
    return ideas
