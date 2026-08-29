"""SEC EDGAR filings overlay for Radar catalyst (free, fail-open)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.config import settings
from app.utils.http_client import shared_client
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_TICKERS_TTL = 86_400.0
_FILINGS_TTL = 1_800.0
CATALYST_FORMS = frozenset({"8-K", "8-K/A", "6-K"})
STATEMENT_FORMS = frozenset({"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A", "40-F"})

_TICKER_CACHE: TTLCache[dict[str, str]] = TTLCache(ttl_seconds=_TICKERS_TTL)


@dataclass(frozen=True)
class EdgarSnapshot:
    """Recent catalyst filings. Missing CIK = empty, not an error."""

    symbol: str
    cik: str | None = None
    eight_k_count: int = 0
    latest_form: str | None = None
    latest_date: date | None = None


_FILING_CACHE: TTLCache[EdgarSnapshot] = TTLCache(ttl_seconds=_FILINGS_TTL)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


def _ticker_map() -> dict[str, str]:
    def _load() -> dict[str, str]:
        client = shared_client(timeout=12.0, name="sec-tickers", headers=_headers())
        response = client.get(_TICKERS_URL)
        response.raise_for_status()
        payload = response.json()
        mapping: dict[str, str] = {}
        if not isinstance(payload, dict):
            return mapping
        for row in payload.values():
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            cik = row.get("cik_str")
            if ticker and cik is not None:
                mapping[ticker] = str(int(cik)).zfill(10)
        return mapping

    try:
        return dict(_TICKER_CACHE.get_or_set("tickers", _load))
    except Exception:
        logger.debug("SEC ticker map skipped", exc_info=True)
        return {}


def lookup_cik(symbol: str) -> str | None:
    return _ticker_map().get(symbol.upper().strip())


def _parse_filings(
    payload: object, *, today: date, window: int
) -> tuple[int, str | None, date | None]:
    filings = payload.get("filings") if isinstance(payload, dict) else None
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return 0, None, None
    forms = recent.get("form")
    dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(dates, list):
        return 0, None, None
    cutoff = today - timedelta(days=window)
    count = 0
    latest_form: str | None = None
    latest_date: date | None = None
    for form, raw_date in zip(forms, dates, strict=False):
        if str(form) not in CATALYST_FORMS:
            continue
        try:
            filed = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            continue
        if filed < cutoff:
            continue
        count += 1
        if latest_date is None or filed > latest_date:
            latest_date = filed
            latest_form = str(form)
    return count, latest_form, latest_date


def iter_recent_filings(payload: object) -> list[tuple[date, str]]:
    """All (filingDate, form) rows from a submissions payload."""
    filings = payload.get("filings") if isinstance(payload, dict) else None
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return []
    forms = recent.get("form")
    dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(dates, list):
        return []
    out: list[tuple[date, str]] = []
    for form, raw_date in zip(forms, dates, strict=False):
        try:
            filed = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            continue
        out.append((filed, str(form)))
    return out


def snapshot_as_of(
    symbol: str,
    filings: tuple[tuple[date, str], ...] | list[tuple[date, str]],
    as_of: date,
    *,
    window_days: int = 14,
    cik: str | None = None,
) -> EdgarSnapshot:
    """8-K / 6-K count in ``[as_of - window, as_of]``. Later filings are ignored."""
    cutoff = as_of - timedelta(days=window_days)
    hits = [
        (filed, form)
        for filed, form in filings
        if form in CATALYST_FORMS and cutoff <= filed <= as_of
    ]
    if not hits:
        return EdgarSnapshot(symbol=symbol.upper().strip(), cik=cik)
    latest_date, latest_form = max(hits, key=lambda item: item[0])
    return EdgarSnapshot(
        symbol=symbol.upper().strip(),
        cik=cik,
        eight_k_count=len(hits),
        latest_form=latest_form,
        latest_date=latest_date,
    )


_HISTORY_CACHE: TTLCache[tuple[tuple[date, str], ...]] = TTLCache(ttl_seconds=_FILINGS_TTL)


def _submissions_payload(cik: str) -> object | None:
    client = shared_client(
        timeout=12.0,
        name="sec-submissions",
        headers=_headers(),
    )
    response = client.get(_SUBMISSIONS_URL.format(cik=cik))
    if response.status_code != 200:
        return None
    return response.json()


def fetch_edgar_filings(symbol: str) -> tuple[tuple[date, str], ...]:
    """Recent EDGAR form/date pairs. Empty tuple when CIK or HTTP fails."""
    normalized = symbol.upper().strip()

    def _load() -> tuple[tuple[date, str], ...]:
        cik = lookup_cik(normalized)
        if not cik:
            return ()
        try:
            payload = _submissions_payload(cik)
        except Exception:
            logger.debug("SEC submissions skipped for %s", normalized, exc_info=True)
            return ()
        if payload is None:
            return ()
        return tuple(iter_recent_filings(payload))

    try:
        return _HISTORY_CACHE.get_or_set(f"hist:{normalized}", _load)
    except Exception:
        return ()


def fetch_edgar_snapshot(
    symbol: str,
    *,
    today: date | None = None,
    window_days: int = 14,
) -> EdgarSnapshot:
    """Recent 8-K / 6-K count. Empty snapshot when CIK or HTTP fails."""
    normalized = symbol.upper().strip()
    now = today or datetime.now(UTC).date()
    key = f"{normalized}:{now.isoformat()}:{window_days}"

    def _load() -> EdgarSnapshot:
        cik = lookup_cik(normalized)
        if not cik:
            return EdgarSnapshot(symbol=normalized)
        try:
            payload = _submissions_payload(cik)
            if payload is None:
                return EdgarSnapshot(symbol=normalized, cik=cik)
            count, form, filed = _parse_filings(payload, today=now, window=window_days)
            return EdgarSnapshot(
                symbol=normalized,
                cik=cik,
                eight_k_count=count,
                latest_form=form,
                latest_date=filed,
            )
        except Exception:
            logger.debug("SEC submissions skipped for %s", normalized, exc_info=True)
            return EdgarSnapshot(symbol=normalized, cik=cik)

    try:
        return _FILING_CACHE.get_or_set(key, _load)
    except Exception:
        return EdgarSnapshot(symbol=normalized)
