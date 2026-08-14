"""Event calendar engine — catalyst and timing risk analysis."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import yfinance as yf

from app.config import settings
from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.symbols import AssetClass, resolve_asset_class
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.http_client import shared_client
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_EVENT_CACHE: TTLCache["EventSnapshot"] = TTLCache(ttl_seconds=900.0)
_FRED_EVENTS_CACHE: TTLCache[list[tuple[str, float]]] = TTLCache(ttl_seconds=900.0)

# FRED release IDs — use /fred/release/dates (singular) with these IDs.
# 180 is Unemployment Insurance Weekly Claims, not FOMC.
_FRED_MACRO_RELEASES: tuple[tuple[str, int], ...] = (
    ("CPI", 10),
    ("Employment Situation", 50),
    ("FOMC Press Release", 101),
)


@dataclass
class EventSnapshot:
    """Upcoming market events relevant to an asset."""

    events: list[str] = field(default_factory=list)
    nearest_days: float | None = None
    score: float = 50.0
    description: str = "Events: no imminent catalysts"


def _parse_datetime(value: object) -> datetime | None:
    """Normalize calendar values to UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _days_until(event_time: datetime, now: datetime) -> float:
    return max((event_time - now).total_seconds() / 86_400, 0.0)


def _score_from_events(events: list[tuple[str, float]]) -> tuple[float, list[str], float | None]:
    """Score timing risk from labeled events with days-until values."""
    if not events:
        return 55.0, [], None

    events.sort(key=lambda item: item[1])
    nearest_days = events[0][1]
    labels = [
        f"{label} in {days:.0f}d" if days >= 1 else f"{label} today"
        for label, days in events[:4]
    ]

    if nearest_days <= 1:
        score = 35.0
    elif nearest_days <= 3:
        score = 42.0
    elif nearest_days <= 7:
        score = 48.0
    else:
        score = 55.0

    return clamp_score(score), labels, nearest_days


def _fetch_fred_macro_events(api_key: str, horizon_days: int = 14) -> list[tuple[str, float]]:
    """Fetch upcoming macro release dates from FRED."""
    now = datetime.now(UTC)
    end = now + timedelta(days=horizon_days)
    found: list[tuple[str, float]] = []

    for label, release_id in _FRED_MACRO_RELEASES:
        params = {
            "release_id": release_id,
            "api_key": api_key,
            "file_type": "json",
            "realtime_start": now.date().isoformat(),
            "realtime_end": end.date().isoformat(),
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": 3,
        }
        try:
            client = shared_client(timeout=5.0, name="fred")
            # Singular /release/dates filters by release_id.
            # Plural /releases/dates returns the global calendar and ignores it.
            response = client.get(
                "https://api.stlouisfed.org/fred/release/dates",
                params=params,
            )
            if response.status_code != 200:
                logger.warning(
                    "FRED release dates for %s (id=%s) returned HTTP %s",
                    label,
                    release_id,
                    response.status_code,
                )
                continue
            for row in response.json().get("release_dates", []):
                event_time = _parse_datetime(row.get("date"))
                if event_time is None:
                    continue
                days = _days_until(event_time, now)
                if days <= horizon_days:
                    found.append((label, days))
                    break
        except Exception:
            logger.exception("Failed to fetch FRED release dates for %s", label)

    return found


def _cached_fred_macro_events(api_key: str) -> list[tuple[str, float]]:
    """Shared FRED calendar — fetched once, reused across all symbols."""
    return _FRED_EVENTS_CACHE.get_or_set("fred_macro", lambda: _fetch_fred_macro_events(api_key))


def _fetch_earnings_event(symbol: str, horizon_days: int = 14) -> list[tuple[str, float]]:
    """Fetch next earnings date for an equity symbol via yfinance."""
    now = datetime.now(UTC)
    try:
        calendar = yf.Ticker(symbol).calendar
    except Exception:
        logger.exception("Failed to fetch earnings calendar for %s", symbol)
        return []

    if not calendar or not isinstance(calendar, dict):
        return []

    earnings_raw = calendar.get("Earnings Date") or calendar.get("Earnings Date High")
    if earnings_raw is None:
        return []

    dates = earnings_raw if isinstance(earnings_raw, list) else [earnings_raw]
    events: list[tuple[str, float]] = []
    for raw in dates:
        event_time = _parse_datetime(raw)
        if event_time is None:
            continue
        days = _days_until(event_time, now)
        if days <= horizon_days:
            events.append((f"{symbol} earnings", days))
            break

    return events


class EventEngine:
    """Flags upcoming catalysts that raise timing risk."""

    def __init__(self, fred_api_key: str | None = None) -> None:
        self._fred_api_key = fred_api_key or settings.fred_api_key

    def snapshot(self, symbol: str, *, include_earnings: bool = False) -> EventSnapshot:
        """Return upcoming events for a symbol (cached ~15 min)."""
        suffix = "earn" if include_earnings else "macro"
        cache_key = f"events:{symbol.upper()}:{suffix}"
        return _EVENT_CACHE.get_or_set(
            cache_key,
            lambda: self._build_snapshot(symbol, include_earnings=include_earnings),
        )

    def _build_snapshot(self, symbol: str, *, include_earnings: bool = False) -> EventSnapshot:
        normalized = symbol.upper()
        asset_class = resolve_asset_class(normalized)
        events: list[tuple[str, float]] = []

        if self._fred_api_key:
            events.extend(_cached_fred_macro_events(self._fred_api_key))

        # Earnings calendars are slow (Yahoo) — only for detail views, not dashboard rank
        if include_earnings and asset_class in {AssetClass.STOCK, AssetClass.ETF}:
            events.extend(_fetch_earnings_event(normalized))

        if not events:
            if asset_class == AssetClass.CRYPTO and not self._fred_api_key:
                message = (
                    "Events: no macro calendar (add FRED_API_KEY); "
                    "crypto unlock feed not yet integrated"
                )
                return EventSnapshot(score=52.0, description=message)
            return EventSnapshot(
                score=55.0,
                description="Events: no imminent catalysts within 14 days",
            )

        score, labels, nearest = _score_from_events(events)
        return EventSnapshot(
            events=labels,
            nearest_days=nearest,
            score=score,
            description=f"Events: {', '.join(labels)}",
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return event calendar evidence (macro calendar; earnings deferred for speed)."""
        del timeframe
        snap = self.snapshot(symbol, include_earnings=False)
        return [
            EvidenceItem(
                source="event_engine",
                category=ScoringCategory.EVENTS.value,
                score=snap.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.EVENTS],
                description=snap.description,
            )
        ]
