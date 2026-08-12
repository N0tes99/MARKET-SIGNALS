"""Scan universe: watchlist equities + Radar seeds + liquid extras + ad-hoc."""

from __future__ import annotations

from collections.abc import Iterable

from app.engines.runner_engine.config import DEFAULT_SEED_UNIVERSE
from app.market_data.symbols import (
    ETF_SYMBOLS,
    STOCK_SYMBOLS,
    looks_like_us_equity_ticker,
)

# Liquid names that often have real option volume and are not always on Surface 1.
EXTRA_LIQUID: tuple[str, ...] = (
    "AVGO",
    "ORCL",
    "MU",
    "INTC",
    "BA",
    "DIS",
    "JPM",
    "XOM",
    "LLY",
    "UNH",
    "CRWD",
    "NET",
    "MARA",
    "RIOT",
    "SOFI",
    "GME",
    "AFRM",
    "CVNA",
    "DKNG",
    "RIVN",
    "BABA",
    "SNAP",
    "PYPL",
    "DELL",
)


def default_tape_universe() -> tuple[str, ...]:
    """Deduped US tickers for the aggressive tape screen."""
    seeds = (*STOCK_SYMBOLS, *ETF_SYMBOLS, *DEFAULT_SEED_UNIVERSE, *EXTRA_LIQUID)
    return merge_extra_symbols((), seeds)


def merge_extra_symbols(base: Iterable[str], extra: Iterable[str] | None) -> tuple[str, ...]:
    """Append valid ad-hoc US tickers without dropping the default set."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in (*base, *(extra or ())):
        name = str(raw).upper().strip()
        if name in seen or not looks_like_us_equity_ticker(name):
            continue
        seen.add(name)
        out.append(name)
    return tuple(out)
