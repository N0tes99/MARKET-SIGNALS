"""CFTC Commitments of Traders overlay for CME Yahoo roots.

Weekly public SODA, no API key. Financials use TFF leveraged money;
commodities use disaggregated managed money. CME crypto (BTC=F / ETH=F /
MBT=F) stays on live crypto funding — this module returns None for those.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.utils.http_client import shared_client
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

TFF_DATASET = "gpe5-46if"
DISAGG_DATASET = "72hh-3qpy"
SODA_BASE = "https://publicreporting.cftc.gov/resource"
HISTORY_LIMIT = 30
MIN_INDEX_WEEKS = 8
MAX_INDEX_WEEKS = 26
CROWDED_HIGH = 80.0
CROWDED_LOW = 20.0
SCORE_TILT = 6.0
_CACHE_TTL_SECONDS = 6 * 3600.0
_HTTP_TIMEOUT = 8.0

CotEffect = Literal["strengthen", "weaken", "neutral"]
CotBook = Literal["tff", "disagg"]


@dataclass(frozen=True)
class CotContractSpec:
    """Yahoo root → CFTC market code + book."""

    yahoo: str
    market_code: str
    book: CotBook


@dataclass(frozen=True)
class CotSnapshot:
    """Latest weekly spec positioning for one Yahoo futures root."""

    symbol: str
    market_code: str
    book: CotBook
    report_date: date
    spec_long: float
    spec_short: float
    spec_net: float
    open_interest: float | None
    cot_index: float | None
    contract_name: str | None = None


@dataclass(frozen=True)
class CotOverlay:
    """Score / copy for the CME board and paper skip."""

    delta: float
    effect: CotEffect
    factor: str | None
    conflict: str | None
    skip_paper: bool


@dataclass(frozen=True)
class _CacheBox:
    snap: CotSnapshot | None


# Skip CME crypto — live crypto funding is the honest crowding print.
CRYPTO_SKIP: frozenset[str] = frozenset({"BTC=F", "ETH=F", "MBT=F"})

COT_CONTRACTS: tuple[CotContractSpec, ...] = (
    CotContractSpec("ES=F", "13874A", "tff"),
    CotContractSpec("NQ=F", "209742", "tff"),
    CotContractSpec("YM=F", "124603", "tff"),
    CotContractSpec("RTY=F", "239742", "tff"),
    CotContractSpec("ZN=F", "043602", "tff"),
    CotContractSpec("ZB=F", "020601", "tff"),
    CotContractSpec("ZF=F", "044601", "tff"),
    CotContractSpec("6E=F", "099741", "tff"),
    CotContractSpec("6J=F", "097741", "tff"),
    CotContractSpec("6B=F", "096742", "tff"),
    CotContractSpec("CL=F", "067651", "disagg"),
    CotContractSpec("NG=F", "023651", "disagg"),
    CotContractSpec("RB=F", "111659", "disagg"),
    CotContractSpec("HO=F", "022651", "disagg"),
    CotContractSpec("GC=F", "088691", "disagg"),
    CotContractSpec("SI=F", "084691", "disagg"),
    CotContractSpec("HG=F", "085692", "disagg"),
    CotContractSpec("PL=F", "076651", "disagg"),
    CotContractSpec("ZC=F", "002602", "disagg"),
    CotContractSpec("ZS=F", "005602", "disagg"),
    CotContractSpec("ZW=F", "001602", "disagg"),
)
COT_BY_YAHOO: dict[str, CotContractSpec] = {c.yahoo: c for c in COT_CONTRACTS}

_CACHE: TTLCache[_CacheBox] = TTLCache(ttl_seconds=_CACHE_TTL_SECONDS)

_TFF_LONG = ("lev_money_positions_long", "lev_money_positions_long_all")
_TFF_SHORT = ("lev_money_positions_short", "lev_money_positions_short_all")
_DISAGG_LONG = ("m_money_positions_long_all", "m_money_positions_long")
_DISAGG_SHORT = ("m_money_positions_short_all", "m_money_positions_short")


def _num(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(raw: object) -> date | None:
    if raw is None or raw == "":
        return None
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _first_num(row: dict[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _num(row.get(key))
        if value is not None:
            return value
    return None


def cot_index(
    nets: list[float],
    *,
    min_weeks: int = MIN_INDEX_WEEKS,
    max_weeks: int = MAX_INDEX_WEEKS,
) -> float | None:
    """Williams-style 0–100 of spec net vs its recent range (oldest first)."""
    if len(nets) < min_weeks:
        return None
    window = nets[-max_weeks:]
    lo = min(window)
    hi = max(window)
    if hi <= lo:
        return 50.0
    return round((window[-1] - lo) / (hi - lo) * 100.0, 1)


def cot_fights_direction(
    direction: str,
    cot_index_value: float | None,
    *,
    high: float = CROWDED_HIGH,
    low: float = CROWDED_LOW,
) -> bool:
    """True when the tape is chasing an extreme spec COT print."""
    if cot_index_value is None:
        return False
    if direction == "long" and cot_index_value >= high:
        return True
    if direction == "short" and cot_index_value <= low:
        return True
    return False


def overlay_for_direction(direction: str | None, snap: CotSnapshot) -> CotOverlay:
    """Strengthen / weaken / skip copy for a board or paper direction."""
    as_of = snap.report_date.isoformat()
    net_txt = f"COT spec net {snap.spec_net:+.0f} as-of {as_of} (weekly)"
    if snap.cot_index is None:
        return CotOverlay(
            delta=0.0,
            effect="neutral",
            factor=net_txt,
            conflict=None,
            skip_paper=False,
        )

    idx = snap.cot_index
    crowded_long = idx >= CROWDED_HIGH
    crowded_short = idx <= CROWDED_LOW
    idx_txt = f"COT index {idx:.0f} as-of {as_of} (weekly)"

    if direction == "long" and crowded_long:
        return CotOverlay(
            delta=-SCORE_TILT,
            effect="weaken",
            factor=idx_txt,
            conflict="COT specs crowded long with the tape",
            skip_paper=True,
        )
    if direction == "short" and crowded_short:
        return CotOverlay(
            delta=-SCORE_TILT,
            effect="weaken",
            factor=idx_txt,
            conflict="COT specs crowded short with the tape",
            skip_paper=True,
        )
    if direction == "long" and crowded_short:
        return CotOverlay(
            delta=SCORE_TILT,
            effect="strengthen",
            factor=f"{idx_txt} — specs extreme short",
            conflict=None,
            skip_paper=False,
        )
    if direction == "short" and crowded_long:
        return CotOverlay(
            delta=SCORE_TILT,
            effect="strengthen",
            factor=f"{idx_txt} — specs extreme long",
            conflict=None,
            skip_paper=False,
        )
    return CotOverlay(
        delta=0.0,
        effect="neutral",
        factor=idx_txt,
        conflict=None,
        skip_paper=False,
    )


def _dataset_url(book: CotBook) -> str:
    dataset = TFF_DATASET if book == "tff" else DISAGG_DATASET
    return f"{SODA_BASE}/{dataset}.json"


def _long_short_keys(book: CotBook) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if book == "tff":
        return _TFF_LONG, _TFF_SHORT
    return _DISAGG_LONG, _DISAGG_SHORT


def _select_clause(book: CotBook) -> str:
    shared = (
        "report_date_as_yyyy_mm_dd,cftc_contract_market_code,"
        "contract_market_name,open_interest_all"
    )
    if book == "tff":
        return f"{shared},lev_money_positions_long,lev_money_positions_short"
    return f"{shared},m_money_positions_long_all,m_money_positions_short_all"


def _http_rows(spec: CotContractSpec) -> list[dict[str, object]]:
    client = shared_client(timeout=_HTTP_TIMEOUT, name="cftc-cot")
    try:
        response = client.get(
            _dataset_url(spec.book),
            params={
                "$select": _select_clause(spec.book),
                "$where": f"cftc_contract_market_code='{spec.market_code}'",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": str(HISTORY_LIMIT),
            },
        )
        if response.status_code >= 400:
            logger.warning(
                "CFTC COT HTTP %s for %s (%s)",
                response.status_code,
                spec.yahoo,
                spec.market_code,
            )
            return []
        payload = response.json()
    except Exception:
        logger.warning("CFTC COT fetch failed for %s", spec.yahoo, exc_info=True)
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _snapshot_from_rows(spec: CotContractSpec, rows: list[dict[str, object]]) -> CotSnapshot | None:
    if not rows:
        return None
    latest_date = rows[0].get("report_date_as_yyyy_mm_dd")
    same_day = [row for row in rows if row.get("report_date_as_yyyy_mm_dd") == latest_date]
    if not same_day:
        same_day = rows[:1]
    best = max(same_day, key=lambda row: _num(row.get("open_interest_all")) or 0.0)
    name = best.get("contract_market_name")
    series = [row for row in rows if row.get("contract_market_name") == name] or [best]
    long_keys, short_keys = _long_short_keys(spec.book)

    nets: list[float] = []
    parsed: list[tuple[date, float, float, float, float | None]] = []
    # API is newest-first; walk reverse so nets are oldest-first.
    for row in reversed(series):
        report = _parse_date(row.get("report_date_as_yyyy_mm_dd"))
        spec_long = _first_num(row, long_keys)
        spec_short = _first_num(row, short_keys)
        if report is None or spec_long is None or spec_short is None:
            continue
        spec_net = spec_long - spec_short
        oi = _num(row.get("open_interest_all"))
        parsed.append((report, spec_long, spec_short, spec_net, oi))
        nets.append(spec_net)
    if not parsed:
        return None
    report, spec_long, spec_short, spec_net, oi = parsed[-1]
    name_txt = str(name) if name else None
    return CotSnapshot(
        symbol=spec.yahoo,
        market_code=spec.market_code,
        book=spec.book,
        report_date=report,
        spec_long=spec_long,
        spec_short=spec_short,
        spec_net=spec_net,
        open_interest=oi,
        cot_index=cot_index(nets),
        contract_name=name_txt,
    )


def _load_snapshot(symbol: str) -> CotSnapshot | None:
    key = symbol.upper().strip()
    if key in CRYPTO_SKIP:
        return None
    spec = COT_BY_YAHOO.get(key)
    if spec is None:
        return None
    return _snapshot_from_rows(spec, _http_rows(spec))


def fetch_cot_snapshot(symbol: str) -> CotSnapshot | None:
    """Latest weekly COT for a Yahoo root. Fail-open (None) on miss/error."""
    key = symbol.upper().strip()

    def _factory() -> _CacheBox:
        return _CacheBox(_load_snapshot(key))

    return _CACHE.get_or_set(key, _factory).snap


def clear_cot_cache() -> None:
    """Test helper."""
    _CACHE.clear()
