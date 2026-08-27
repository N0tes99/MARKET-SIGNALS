"""Headline polarity v0 — RSS titles only, not a 13-category grade input."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.market_data.symbols import AssetClass, resolve_asset_class
from app.utils.http_client import shared_client
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_CACHE: TTLCache[HeadlineBundle] = TTLCache(ttl_seconds=900.0)
_YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline"

_BULL = (
    "surge",
    "rally",
    "jump",
    "soar",
    "beat",
    "beats",
    "record",
    "approval",
    "etf inflow",
    "breakout",
    "bullish",
)
_BEAR = (
    "plunge",
    "crash",
    "tumble",
    "miss",
    "misses",
    "fraud",
    "hack",
    "lawsuit",
    "ban",
    "outflow",
    "bearish",
    "sec charges",
)


@dataclass(frozen=True)
class HeadlineBundle:
    """Cheap title polarity. Empty titles = no read."""

    score: float = 50.0
    direction: str | None = None
    titles: list[str] = field(default_factory=list)
    source: str = "yahoo-rss"


def yahoo_rss_symbol(symbol: str) -> str:
    """Map desk symbols onto Yahoo RSS tickers."""
    normalized = symbol.upper().strip()
    try:
        cls = resolve_asset_class(normalized)
    except Exception:
        cls = None
    if cls == AssetClass.CRYPTO:
        return f"{normalized}-USD"
    return normalized


def score_titles(titles: list[str]) -> tuple[float, str | None]:
    """Keyword polarity on titles. Neutral when nothing matches."""
    bull = 0
    bear = 0
    for title in titles:
        blob = title.lower()
        bull += sum(1 for word in _BULL if word in blob)
        bear += sum(1 for word in _BEAR if word in blob)
    if bull == 0 and bear == 0:
        return 50.0, None
    score = clamp_score(50.0 + 10.0 * (bull - bear))
    if bull > bear:
        return score, "up"
    if bear > bull:
        return score, "down"
    return 50.0, None


def parse_rss_titles(xml_text: str, *, limit: int = 8) -> list[str]:
    """Pull item titles from an RSS 2.0 document."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    titles: list[str] = []
    for item in root.findall(".//item"):
        node = item.find("title")
        if node is None or not (node.text or "").strip():
            continue
        titles.append(node.text.strip())
        if len(titles) >= limit:
            break
    return titles


def fetch_headline_bundle(symbol: str) -> HeadlineBundle:
    """Yahoo RSS titles + keyword score. Fail-open to empty."""
    key = symbol.upper().strip()

    def _load() -> HeadlineBundle:
        ticker = yahoo_rss_symbol(key)
        try:
            client = shared_client(timeout=6.0, name="headline-rss")
            response = client.get(
                _YAHOO_RSS,
                params={"s": ticker, "region": "US", "lang": "en-US"},
            )
            if response.status_code != 200:
                return HeadlineBundle()
            titles = parse_rss_titles(response.text)
        except Exception:
            logger.debug("headline RSS skipped for %s", key, exc_info=True)
            return HeadlineBundle()
        score, direction = score_titles(titles)
        return HeadlineBundle(score=score, direction=direction, titles=titles)

    try:
        return _CACHE.get_or_set(key, _load)
    except Exception:
        logger.debug("headline cache skipped for %s", key, exc_info=True)
        return HeadlineBundle()
