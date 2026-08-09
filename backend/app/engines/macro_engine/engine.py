"""Macro Engine — macroeconomic context tracking."""

import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.engines.evidence_engine.types import EvidenceItem
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_MACRO_CACHE: TTLCache["MacroSnapshot"] = TTLCache(ttl_seconds=900.0)


@dataclass
class MacroSnapshot:
    """Current macroeconomic context snapshot."""

    dxy: float | None = None
    treasury_10y: float | None = None
    fed_funds_rate: float | None = None
    cpi_yoy: float | None = None
    unemployment_rate: float | None = None
    upcoming_events: list[str] = field(default_factory=list)
    score: float = 50.0
    description: str = "Macro context neutral"


class MacroEngine:
    """Tracks and analyzes macroeconomic indicators."""

    def __init__(self, fred_api_key: str | None = None) -> None:
        """Initialize with optional FRED API key."""
        self._fred_api_key = fred_api_key or settings.fred_api_key

    def _fetch_fred_series(self, series_id: str) -> float | None:
        """Fetch the latest observation from FRED if API key is configured."""
        if not self._fred_api_key:
            return None

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self._fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url, params=params)
                if response.status_code != 200:
                    # Soft-fail per series — do not poison the rest of the snapshot.
                    logger.warning(
                        "FRED series %s returned HTTP %s",
                        series_id,
                        response.status_code,
                    )
                    return None
                observations = response.json().get("observations", [])
                if observations and observations[0]["value"] != ".":
                    return float(observations[0]["value"])
        except Exception:
            logger.exception("Failed to fetch FRED series %s", series_id)

        return None

    def snapshot(self) -> MacroSnapshot:
        """Return current macroeconomic context (cached ~15 min)."""
        return _MACRO_CACHE.get_or_set("macro_snapshot", self._fetch_snapshot)

    def _fetch_snapshot(self) -> MacroSnapshot:
        """Fetch macro data from FRED."""
        dxy = self._fetch_fred_series("DTWEXBGS")
        treasury = self._fetch_fred_series("DGS10")
        fed_funds = self._fetch_fred_series("FEDFUNDS")
        unemployment = self._fetch_fred_series("UNRATE")

        scores: list[float] = []
        factors: list[str] = []

        if dxy is not None:
            # Strong dollar is typically a headwind for risk assets like crypto
            scores.append(clamp_score(60 - (dxy - 100) * 2))
            factors.append(f"DXY {dxy:.1f}")

        if treasury is not None:
            # Moderate yields are neutral; very high yields tighten financial conditions
            if treasury <= 4.0:
                scores.append(55.0)
            elif treasury <= 5.0:
                scores.append(45.0)
            else:
                scores.append(35.0)
            factors.append(f"10Y yield {treasury:.2f}%")

        if fed_funds is not None:
            # Lower rates generally support risk assets
            if fed_funds <= 3.0:
                scores.append(60.0)
            elif fed_funds <= 5.0:
                scores.append(50.0)
            else:
                scores.append(40.0)
            factors.append(f"Fed funds {fed_funds:.2f}%")

        if unemployment is not None:
            # Low unemployment supports risk appetite
            if unemployment <= 4.5:
                scores.append(55.0)
            else:
                scores.append(45.0)
            factors.append(f"Unemployment {unemployment:.1f}%")

        if scores:
            score = clamp_score(sum(scores) / len(scores))
            description = f"Macro: {', '.join(factors)}"
        elif not self._fred_api_key:
            score = 50.0
            description = "Macro: neutral context (add FRED_API_KEY to .env for live data)"
        else:
            # Key present but every series soft-failed — stay neutral, not crashing.
            score = 50.0
            description = "Macro: FRED unavailable (neutral context; data quality degraded)"

        return MacroSnapshot(
            dxy=dxy,
            treasury_10y=treasury,
            fed_funds_rate=fed_funds,
            unemployment_rate=unemployment,
            score=score,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return macro evidence item (global, not per-symbol)."""
        del symbol, timeframe
        snap = self.snapshot()
        return [
            EvidenceItem(
                source="macro_engine",
                category=ScoringCategory.MACRO.value,
                score=snap.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.MACRO],
                description=snap.description,
            ),
        ]
