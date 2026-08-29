"""SEC 13F-HR full-text search for Radar replay institutional_accum.

13F-HR is filed by *managers*, not issuers. Issuer CIK submissions do not
contain 13F-HR. This v0 searches EFTS for the issuer title (and longer tickers)
and counts unique filer CIKs over time. That is not a complete manager universe
and not a % owned. Knowable date is ``file_date`` only — never period ending.

Live Yahoo ``heldPercentInstitutions`` is never written into replay.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.config import settings
from app.engines.runner_engine.scoring.edgar import lookup_issuer_title
from app.engines.runner_engine.types import DimensionScore
from app.utils.http_client import shared_client
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_CACHE_TTL = 1_800.0
_PAGE_SIZE = 100
_HITS_CAP = 250
# 5y study bars + 2y YoY lookback, plus the current partial year.
_SEARCH_YEARS = 8
_WINDOW_DAYS = 365
MIN_TICKER_QUERY_LEN = 4
INCOMPLETE_UNIVERSE_FACTOR = (
    "13F EDGAR search (not a complete manager universe)"
)
# Single value: EFTS keeps the last repeated ``forms`` param, so listing
# 13F-HR then 13F-HR/A would search amendments only. ``13F-HR`` already
# matches 13F-HR/A via root_forms.
_FORM = "13F-HR"


@dataclass(frozen=True)
class ThirteenFHit:
    """One EFTS 13F hit. ``file_date`` is the only knowable instant."""

    accession: str
    file_date: date
    filer_cik: str | None
    form: str = "13F-HR"


@dataclass(frozen=True)
class ThirteenFSearchResult:
    """Cached EFTS hits for one issuer query set."""

    hits: tuple[ThirteenFHit, ...]
    capped: bool = False
    incomplete: bool = False
    coverage_start: date | None = None


_CACHE: TTLCache[ThirteenFSearchResult] = TTLCache(ttl_seconds=_CACHE_TTL)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": settings.sec_user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }


def search_queries(symbol: str, title: str | None) -> tuple[str, ...]:
    """Quoted issuer title first. Short tickers (CLS, KO, VRT) are not queries."""
    queries: list[str] = []
    cleaned_title = (title or "").strip()
    if cleaned_title:
        queries.append(f'"{cleaned_title}"')
    ticker = symbol.upper().strip()
    if len(ticker) >= MIN_TICKER_QUERY_LEN:
        queries.append(ticker)
    return tuple(queries)


def _parse_file_date(raw: object) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_cik(raw: object) -> str | None:
    if raw is None:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if not digits:
        return None
    try:
        return str(int(digits)).zfill(10)
    except ValueError:
        return None


def _hit_source(hit: object) -> dict:
    if not isinstance(hit, dict):
        return {}
    src = hit.get("_source")
    if isinstance(src, dict):
        return src
    return hit


def parse_efts_hits(payload: object) -> list[ThirteenFHit]:
    """Parse an EFTS search-index JSON body into 13F hits."""
    root = payload.get("hits") if isinstance(payload, dict) else None
    rows = root.get("hits") if isinstance(root, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[ThirteenFHit] = []
    seen: set[str] = set()
    for row in rows:
        src = _hit_source(row)
        form = str(src.get("form") or src.get("file_type") or "13F-HR")
        if not form.upper().startswith("13F-HR"):
            continue
        filed = _parse_file_date(src.get("file_date") or src.get("fileDt"))
        if filed is None:
            continue
        accession = str(src.get("adsh") or "")
        if not accession and isinstance(row, dict):
            accession = str(row.get("_id") or "")
        accession = accession.split(":")[0].strip()
        if not accession or accession in seen:
            continue
        ciks = src.get("ciks")
        filer: str | None = None
        if isinstance(ciks, list) and ciks:
            filer = _parse_cik(ciks[0])
        if filer is None:
            filer = _parse_cik(src.get("cik"))
        seen.add(accession)
        out.append(
            ThirteenFHit(
                accession=accession,
                file_date=filed,
                filer_cik=filer,
                form=form,
            )
        )
    return out


def _total_hits(payload: object) -> int:
    root = payload.get("hits") if isinstance(payload, dict) else None
    if not isinstance(root, dict):
        return 0
    total = root.get("total")
    if isinstance(total, dict):
        try:
            return int(total.get("value") or 0)
        except (TypeError, ValueError):
            return 0
    try:
        return int(total or 0)
    except (TypeError, ValueError):
        return 0


def _search_windows(
    *,
    as_of: date | None = None,
    years: int = _SEARCH_YEARS,
) -> tuple[tuple[date, date], ...]:
    end = as_of or datetime.now(UTC).date()
    windows: list[tuple[date, date]] = []
    for i in range(years):
        year = end.year - i
        start = date(year, 1, 1)
        stop = end if year == end.year else date(year, 12, 31)
        if start <= stop:
            windows.append((start, stop))
    return tuple(windows)


def efts_search_params(
    query: str,
    start: date,
    end: date,
    *,
    offset: int = 0,
    size: int = _PAGE_SIZE,
) -> list[tuple[str, str]]:
    """EFTS query string. One ``forms`` value — last-wins on duplicates."""
    return [
        ("q", query),
        ("dateRange", "custom"),
        ("startdt", start.isoformat()),
        ("enddt", end.isoformat()),
        ("from", str(offset)),
        ("size", str(size)),
        ("forms", _FORM),
    ]


def _efts_page(
    query: str,
    start: date,
    end: date,
    *,
    offset: int,
) -> object | None:
    client = shared_client(timeout=12.0, name="sec-efts", headers=_headers())
    response = client.get(
        _EFTS_URL,
        params=efts_search_params(query, start, end, offset=offset),
    )
    if response.status_code != 200:
        return None
    return response.json()


def _search_query_window(
    query: str, start: date, end: date
) -> tuple[list[ThirteenFHit], bool, bool]:
    hits: list[ThirteenFHit] = []
    capped = False
    offset = 0
    while offset < _HITS_CAP:
        try:
            payload = _efts_page(query, start, end, offset=offset)
        except Exception:
            logger.debug("EFTS 13F search skipped", exc_info=True)
            return hits, capped, True
        if payload is None:
            return hits, capped, True
        page = parse_efts_hits(payload)
        hits.extend(page)
        total = _total_hits(payload)
        offset += _PAGE_SIZE
        if offset >= _HITS_CAP and (total > _HITS_CAP or len(page) >= _PAGE_SIZE):
            capped = True
            break
        if len(page) < _PAGE_SIZE or offset >= total:
            break
    if len(hits) >= _HITS_CAP:
        capped = True
        hits = hits[:_HITS_CAP]
    return hits, capped, False


def _dedupe(hits: list[ThirteenFHit]) -> tuple[ThirteenFHit, ...]:
    seen: set[str] = set()
    out: list[ThirteenFHit] = []
    for hit in hits:
        if hit.accession in seen:
            continue
        seen.add(hit.accession)
        out.append(hit)
    return tuple(out)


def fetch_thirteen_f_search(symbol: str) -> ThirteenFSearchResult:
    """EFTS 13F-HR hits for an issuer. Empty result on any failure."""
    normalized = symbol.upper().strip()

    def _load() -> ThirteenFSearchResult:
        title = lookup_issuer_title(normalized)
        queries = search_queries(normalized, title)
        if not queries:
            return ThirteenFSearchResult(hits=())
        collected: list[ThirteenFHit] = []
        capped = False
        incomplete = False
        completed_starts: list[date] = []
        for query in queries:
            for start, end in _search_windows():
                page_hits, page_capped, failed = _search_query_window(query, start, end)
                collected.extend(page_hits)
                capped = capped or page_capped
                if failed:
                    incomplete = True
                else:
                    completed_starts.append(start)
        coverage_start = min(completed_starts) if completed_starts else None
        return ThirteenFSearchResult(
            hits=_dedupe(collected),
            capped=capped,
            incomplete=incomplete,
            coverage_start=coverage_start,
        )

    try:
        return _CACHE.get_or_set(f"13f:{normalized}", _load)
    except Exception:
        logger.debug("13F search skipped for %s", normalized, exc_info=True)
        return ThirteenFSearchResult(hits=())


def thirteen_f_event_dates(result: ThirteenFSearchResult) -> tuple[date, ...]:
    return tuple(sorted({hit.file_date for hit in result.hits}))


def _unique_filers(
    hits: tuple[ThirteenFHit, ...],
    *,
    start: date,
    end: date,
) -> set[str]:
    filers: set[str] = set()
    for hit in hits:
        if hit.filer_cik and start < hit.file_date <= end:
            filers.add(hit.filer_cik)
    return filers


def score_institutional_13f(
    result: ThirteenFSearchResult,
    as_of: date,
    *,
    window_days: int = _WINDOW_DAYS,
) -> DimensionScore:
    """Trailing-year vs prior-year unique 13F filer CIKs, knowable by ``as_of``."""
    current_start = as_of - timedelta(days=window_days)
    prior_start = as_of - timedelta(days=window_days * 2)
    current = _unique_filers(result.hits, start=current_start, end=as_of)
    prior = _unique_filers(result.hits, start=prior_start, end=current_start)
    factors = [INCOMPLETE_UNIVERSE_FACTOR]
    conflicts: list[str] = []
    if result.capped:
        factors.append("search result cap reached — incomplete")
    if result.incomplete:
        factors.append("partial 13F search — trend not scored")
        return DimensionScore(
            name="institutional_accum",
            score=50.0,
            confidence=0.25,
            factors=factors,
            conflicts=conflicts,
            data_quality="missing",
        )
    if result.coverage_start is not None and prior_start < result.coverage_start:
        factors.append("prior-year 13F window not in search coverage")
        return DimensionScore(
            name="institutional_accum",
            score=50.0,
            confidence=0.25,
            factors=factors,
            conflicts=conflicts,
            data_quality="missing",
        )

    if not current and not prior:
        factors.append("No 13F search hits knowable by this as-of")
        return DimensionScore(
            name="institutional_accum",
            score=50.0,
            confidence=0.25,
            factors=factors,
            conflicts=conflicts,
            data_quality="missing",
        )

    n_current = len(current)
    n_prior = len(prior)
    if n_prior == 0:
        change_pct = 100.0 if n_current > 0 else 0.0
    else:
        change_pct = 100.0 * (n_current - n_prior) / n_prior
    score = clamp_score(50.0 + change_pct * 0.25)
    coverage = f"{n_current} unique 13F filers in trailing year vs {n_prior} prior year"
    factors.append(coverage)
    if n_current > n_prior:
        factors.append("Rising 13F filer coverage")
    elif n_current < n_prior:
        conflicts.append("Shrinking 13F filer coverage")
    else:
        factors.append("Stable 13F filer coverage")

    return DimensionScore(
        name="institutional_accum",
        score=score,
        confidence=0.45,
        factors=factors,
        conflicts=conflicts,
        data_quality="degraded",
    )
