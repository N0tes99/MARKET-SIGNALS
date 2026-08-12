"""Alpaca Market Data — FREE-tier IEX stock snapshots only.

Uses the same Trading API keys (APCA-API-KEY-ID / SECRET) against
``https://data.alpaca.markets``. Always requests ``feed=iex`` — never SIP
or any paid consolidated feed (Algo Trader Plus).

Soft-fails on 401/403/404/429 so ranking / dashboard never break.
Yahoo remains the primary OHLCV source; this is activity display only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.brokers.alpaca import alpaca_configured
from app.config import settings
from app.market_data.symbols import (
    ETF_SYMBOLS,
    STOCK_SYMBOLS,
    AssetClass,
    get_asset_class,
)
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_DEFAULT_DATA_URL = "https://data.alpaca.markets"
_FREE_FEED = "iex"
_CACHE_TTL_SECONDS = 60.0
_MAX_SYMBOLS = 40
_BATCH_SIZE = 20
_SOFT_FAIL_STATUSES = frozenset({401, 403, 404, 429})

_ACTIVITY_CACHE: TTLCache[AlpacaActivitySnapshot] = TTLCache(
    ttl_seconds=_CACHE_TTL_SECONDS
)

# Equity/ETF universe eligible for IEX stock snapshots (no crypto).
_EQUITY_UNIVERSE: frozenset[str] = frozenset(STOCK_SYMBOLS + ETF_SYMBOLS)


@dataclass(frozen=True)
class AlpacaActivityRow:
    """Per-symbol IEX activity from a stock snapshot."""

    symbol: str
    last_price: float | None
    daily_volume: float | None
    change_pct: float | None  # fraction, e.g. 0.012 = +1.2%
    daily_bar_close: float | None = None
    prev_close: float | None = None
    trade_time: datetime | None = None


@dataclass
class AlpacaActivitySnapshot:
    """Dashboard payload for free-tier Alpaca IEX activity."""

    configured: bool
    feed: str
    data_base_url: str
    as_of: datetime
    cached: bool = False
    error: str | None = None
    symbols_requested: list[str] = field(default_factory=list)
    rows: list[AlpacaActivityRow] = field(default_factory=list)


def _resolve_data_base_url() -> str:
    override = (settings.alpaca_data_base_url or "").strip().rstrip("/")
    if not override:
        return _DEFAULT_DATA_URL
    lowered = override.lower()
    for suffix in ("/v2/stocks", "/v2"):
        if lowered.endswith(suffix):
            override = override[: -len(suffix)].rstrip("/")
            break
    return override


def _auth_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key.strip(),
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret.strip(),
        "Accept": "application/json",
    }


def _parse_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_equity_or_etf(symbol: str) -> bool:
    try:
        asset = get_asset_class(symbol)
    except Exception:
        return symbol.upper() in _EQUITY_UNIVERSE
    return asset in {AssetClass.STOCK, AssetClass.ETF}


def normalize_activity_symbols(
    symbols: list[str] | None,
    *,
    limit: int = _MAX_SYMBOLS,
) -> list[str]:
    """Filter to unique equity/ETF symbols; drop crypto; cap length."""
    if not symbols:
        # Default: tracked stocks + ETFs (ranked list order not required).
        candidates = list(STOCK_SYMBOLS + ETF_SYMBOLS)
    else:
        candidates = [s.strip().upper() for s in symbols if s and s.strip()]

    seen: set[str] = set()
    out: list[str] = []
    for sym in candidates:
        if sym in seen:
            continue
        if not _is_equity_or_etf(sym):
            continue
        seen.add(sym)
        out.append(sym)
        if len(out) >= limit:
            break
    return out


def _parse_snapshot_row(symbol: str, payload: dict[str, Any]) -> AlpacaActivityRow:
    trade = payload.get("latestTrade")
    if not isinstance(trade, dict):
        trade = {}
    daily = payload.get("dailyBar")
    if not isinstance(daily, dict):
        daily = {}
    prev = payload.get("prevDailyBar")
    if not isinstance(prev, dict):
        prev = {}

    last_price = _parse_float(trade.get("p"))
    daily_close = _parse_float(daily.get("c"))
    prev_close = _parse_float(prev.get("c"))
    volume = _parse_float(daily.get("v"))

    change_pct: float | None = None
    ref = prev_close
    if ref is None or ref == 0:
        # Fall back to daily open for intraday change when prev bar missing.
        ref = _parse_float(daily.get("o"))
    price_for_change = last_price if last_price is not None else daily_close
    if price_for_change is not None and ref is not None and ref != 0:
        change_pct = (price_for_change - ref) / ref

    return AlpacaActivityRow(
        symbol=symbol,
        last_price=last_price,
        daily_volume=volume,
        change_pct=change_pct,
        daily_bar_close=daily_close,
        prev_close=prev_close,
        trade_time=_parse_dt(trade.get("t")),
    )


def _unconfigured() -> AlpacaActivitySnapshot:
    return AlpacaActivitySnapshot(
        configured=False,
        feed=_FREE_FEED,
        data_base_url="",
        as_of=datetime.now(UTC),
        error=None,
        symbols_requested=[],
        rows=[],
    )


def _cache_key(symbols: list[str]) -> str:
    return "activity:" + ",".join(symbols)


def _fetch_batch(
    client: httpx.Client,
    base_url: str,
    batch: list[str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (snapshots_map, error). Soft-fail statuses become (None, msg)."""
    # Hard constraint: always iex — never sip / delayed_sip / boats.
    params = {
        "symbols": ",".join(batch),
        "feed": _FREE_FEED,
    }
    assert params["feed"] == "iex"
    url = f"{base_url}/v2/stocks/snapshots"
    resp = client.get(url, params=params)

    if resp.status_code in _SOFT_FAIL_STATUSES:
        detail = (resp.text or "")[:160]
        logger.warning(
            "Alpaca IEX snapshots soft-fail HTTP %s symbols=%s: %s",
            resp.status_code,
            ",".join(batch[:8]),
            detail,
        )
        return None, f"Alpaca market data error ({resp.status_code})"

    if resp.status_code >= 400:
        detail = (resp.text or "")[:160]
        logger.warning(
            "Alpaca IEX snapshots HTTP %s: %s", resp.status_code, detail
        )
        return None, f"Alpaca market data error ({resp.status_code})"

    payload = resp.json()
    if not isinstance(payload, dict):
        return None, "Alpaca market data returned unexpected payload"
    return payload, None


def _fetch_activity_uncached(symbols: list[str]) -> AlpacaActivitySnapshot:
    if not alpaca_configured():
        return _unconfigured()

    normalized = normalize_activity_symbols(symbols)
    base_url = _resolve_data_base_url()
    as_of = datetime.now(UTC)

    if not normalized:
        return AlpacaActivitySnapshot(
            configured=True,
            feed=_FREE_FEED,
            data_base_url=base_url,
            as_of=as_of,
            error=None,
            symbols_requested=[],
            rows=[],
        )

    rows: list[AlpacaActivityRow] = []
    errors: list[str] = []

    try:
        with httpx.Client(timeout=12.0, headers=_auth_headers()) as client:
            for i in range(0, len(normalized), _BATCH_SIZE):
                batch = normalized[i : i + _BATCH_SIZE]
                payload, err = _fetch_batch(client, base_url, batch)
                if err:
                    errors.append(err)
                    # Soft-fail: keep any prior batches; do not raise.
                    continue
                assert payload is not None
                for sym in batch:
                    raw = payload.get(sym)
                    if not isinstance(raw, dict):
                        # Case variants occasionally appear.
                        raw = payload.get(sym.upper()) or payload.get(sym.lower())
                    if not isinstance(raw, dict):
                        continue
                    rows.append(_parse_snapshot_row(sym, raw))
    except Exception:
        logger.exception("Alpaca IEX activity fetch failed")
        return AlpacaActivitySnapshot(
            configured=True,
            feed=_FREE_FEED,
            data_base_url=base_url,
            as_of=as_of,
            error="Alpaca market data unavailable",
            symbols_requested=normalized,
            rows=[],
        )

    # Prefer symbols with volume / price; stable order by abs change then volume.
    rows.sort(
        key=lambda r: (
            abs(r.change_pct or 0.0),
            r.daily_volume or 0.0,
        ),
        reverse=True,
    )

    error = None
    if errors and not rows:
        error = errors[0]
    elif errors and rows:
        error = f"{errors[0]} (partial)"

    return AlpacaActivitySnapshot(
        configured=True,
        feed=_FREE_FEED,
        data_base_url=base_url,
        as_of=as_of,
        cached=False,
        error=error,
        symbols_requested=normalized,
        rows=rows,
    )


def fetch_alpaca_activity(
    symbols: list[str] | None = None,
    *,
    use_cache: bool = True,
) -> AlpacaActivitySnapshot:
    """Fetch free-tier IEX snapshots for equity/ETF symbols (cached ~60s)."""
    if not alpaca_configured():
        return _unconfigured()

    normalized = normalize_activity_symbols(symbols)
    if not use_cache:
        return _fetch_activity_uncached(normalized)

    key = _cache_key(normalized)
    hit = _ACTIVITY_CACHE.get(key)
    if hit is not None:
        return AlpacaActivitySnapshot(
            configured=hit.configured,
            feed=hit.feed,
            data_base_url=hit.data_base_url,
            as_of=hit.as_of,
            cached=True,
            error=hit.error,
            symbols_requested=list(hit.symbols_requested),
            rows=list(hit.rows),
        )

    snap = _fetch_activity_uncached(normalized)
    snap.cached = False
    _ACTIVITY_CACHE.set(key, snap)
    return snap


def clear_alpaca_activity_cache() -> None:
    """Test helper — drop in-memory activity cache."""
    _ACTIVITY_CACHE.clear()
