"""Liquidation aggregates — Coinglass overlay plus public OKX/Bybit REST.

Coinglass stays optional. Without a key (or on a Coinglass miss) we scan recent
public liquidation fills from OKX, then Bybit.

USD mapping
-----------
OKX SWAP: ``usd = sz * ctVal * bkPx`` (contracts × contract value × bankruptcy
price). ``ctVal`` comes from ``/api/v5/public/instruments`` and is cached per
``instId``. Long liq = forced sell of longs (``posSide=long`` / ``side=sell``).
Short liq = forced cover of shorts (``posSide=short`` / ``side=buy``).

Bybit linear: ``usd = size * price``. Buy update = long liquidated; Sell =
short liquidated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.utils.http_client import shared_client
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_OKX_BASE = "https://www.okx.com"
_BYBIT_BASE = "https://api.bybit.com"
_SOFT_FAIL_STATUS = frozenset({403, 404, 418, 429, 451})
_FOUR_H_MIN_MS = int(3.5 * 60 * 60 * 1000)
_FOUR_H_MAX_MS = int(5.5 * 60 * 60 * 1000)


@dataclass(frozen=True)
class LiquidationSnapshot:
    """Latest aggregated long/short liquidation USD for a coin."""

    symbol: str
    long_usd: float
    short_usd: float
    interval: str = "4h"

    @property
    def total_usd(self) -> float:
        return self.long_usd + self.short_usd

    @property
    def long_share(self) -> float:
        if self.total_usd <= 0:
            return 0.5
        return self.long_usd / self.total_usd


_LIQ_CACHE: TTLCache[LiquidationSnapshot | None] = TTLCache(ttl_seconds=180.0)
_CTVAL_CACHE: TTLCache[float | None] = TTLCache(ttl_seconds=3600.0)


def score_liquidations(snap: LiquidationSnapshot) -> tuple[float, str]:
    """Map long/short liquidation imbalance to a Derivatives tilt.

    Dominant **long** liquidations (forced sells) → mild constructive relief.
    Dominant **short** liquidations (forced covers) → mild chase / squeeze caution.
    """
    if snap.total_usd <= 0:
        return 50.0, "liquidations flat"

    share = snap.long_share
    imbalance = abs(share - 0.5) * 2.0  # 0..1
    score = 50.0

    if share >= 0.62:
        score = 50.0 + 8.0 + imbalance * 6.0
        side = "longs flushed"
    elif share <= 0.38:
        score = 50.0 - 8.0 - imbalance * 6.0
        side = "shorts flushed"
    else:
        side = "balanced wipe"

    if snap.total_usd >= 50_000_000:
        score += 2.0 if score >= 50 else -2.0
        size_note = f"${snap.total_usd / 1e6:.0f}M"
    elif snap.total_usd >= 10_000_000:
        size_note = f"${snap.total_usd / 1e6:.1f}M"
    else:
        size_note = f"${snap.total_usd / 1e3:.0f}K"

    desc = (
        f"Liqs {snap.interval} {size_note} "
        f"(L ${snap.long_usd / 1e6:.2f}M / S ${snap.short_usd / 1e6:.2f}M) — {side}"
    )
    return clamp_score(score), desc


def fetch_aggregated_liquidations(
    symbol: str,
    *,
    interval: str = "4h",
    limit: int = 6,
) -> LiquidationSnapshot | None:
    """Fetch recent aggregated coin liquidations; None on empty/geo/failure.

    Coinglass is used when ``COINGLASS_API_KEY`` is set. Otherwise (or on a
    Coinglass miss) public OKX filled liquidation orders are scanned, then
    Bybit. Interval is the Coinglass bucket when that path hits; exchange
    rows are labeled ``okx`` / ``bybit`` unless timestamps clearly span ~4h.
    """
    normalized = symbol.upper()
    cache_key = f"{normalized}:{interval}:{limit}"

    def _load() -> LiquidationSnapshot | None:
        key = (settings.coinglass_api_key or "").strip()
        if key:
            snap = _fetch_coinglass(
                normalized, interval=interval, limit=limit, api_key=key
            )
            if snap is not None:
                return snap
        snap = _fetch_okx_liquidations(normalized)
        if snap is not None:
            return snap
        return _fetch_bybit_liquidations(normalized)

    return _LIQ_CACHE.get_or_set(cache_key, _load)


def _soft_get_json(client, url: str, params: dict) -> dict | None:
    """GET JSON; geo/auth blocks and transport errors are soft misses."""
    try:
        response = client.get(url, params=params)
        if response.status_code in _SOFT_FAIL_STATUS:
            logger.debug(
                "Liquidations HTTP %s for %s params=%s",
                response.status_code,
                url,
                params,
            )
            return None
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.debug("Liquidations fetch failed for %s", url, exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


def _parse_ts_ms(row: dict) -> int | None:
    raw = row.get("ts") or row.get("time") or row.get("T") or row.get("updatedTime")
    if raw in (None, ""):
        return None
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    # Seconds vs milliseconds.
    if value < 10_000_000_000:
        value *= 1000
    return value


def _honest_interval(source: str, timestamps_ms: list[int]) -> str:
    """Use ``4h`` only when timestamps actually span about four hours."""
    if len(timestamps_ms) < 2:
        return source
    span = max(timestamps_ms) - min(timestamps_ms)
    if _FOUR_H_MIN_MS <= span <= _FOUR_H_MAX_MS:
        return "4h"
    return source


def _snapshot_from_events(
    symbol: str,
    source: str,
    events: list[tuple[int | None, float, bool]],
) -> LiquidationSnapshot | None:
    long_usd = 0.0
    short_usd = 0.0
    timestamps: list[int] = []
    for ts, usd, is_long in events:
        if usd <= 0:
            continue
        if is_long:
            long_usd += usd
        else:
            short_usd += usd
        if ts:
            timestamps.append(ts)
    if long_usd <= 0 and short_usd <= 0:
        return None
    return LiquidationSnapshot(
        symbol=symbol,
        long_usd=long_usd,
        short_usd=short_usd,
        interval=_honest_interval(source, timestamps),
    )


def _okx_is_long_liq(row: dict) -> bool | None:
    """Long liq = forced sell of longs; short liq = forced cover of shorts."""
    pos = str(row.get("posSide") or "").strip().lower()
    if pos == "long":
        return True
    if pos == "short":
        return False
    side = str(row.get("side") or "").strip().lower()
    if side == "sell":
        return True
    if side == "buy":
        return False
    return None


def _okx_ct_val(inst_id: str) -> float | None:
    """Contract value in base coin; cached per instrument."""

    def _load() -> float | None:
        client = shared_client(timeout=5.0, name="okx")
        payload = _soft_get_json(
            client,
            f"{_OKX_BASE}/api/v5/public/instruments",
            {"instType": "SWAP", "instId": inst_id},
        )
        if not payload or str(payload.get("code")) != "0":
            return None
        rows = payload.get("data") or []
        if not isinstance(rows, list) or not rows:
            return None
        raw = rows[0].get("ctVal") if isinstance(rows[0], dict) else None
        try:
            value = float(raw or 0)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    return _CTVAL_CACHE.get_or_set(inst_id, _load)


def _fetch_okx_liquidations(symbol: str) -> LiquidationSnapshot | None:
    """Recent filled SWAP liquidations. ``uly=BTC-USDT`` (not instId-only)."""
    uly = f"{symbol}-USDT"
    default_inst = f"{symbol}-USDT-SWAP"
    try:
        client = shared_client(timeout=5.0, name="okx")
        payload = _soft_get_json(
            client,
            f"{_OKX_BASE}/api/v5/public/liquidation-orders",
            {"instType": "SWAP", "uly": uly, "state": "filled"},
        )
        if not payload or str(payload.get("code")) != "0":
            return None
        blocks = payload.get("data") or []
        if not isinstance(blocks, list) or not blocks:
            return None

        events: list[tuple[int | None, float, bool]] = []
        for block in blocks:
            if not isinstance(block, dict) or block.get("$ref"):
                continue
            details = block.get("details") or []
            if not isinstance(details, list):
                continue
            inst_id = str(block.get("instId") or default_inst)
            ct_val = _okx_ct_val(inst_id)
            if ct_val is None:
                continue
            for row in details:
                if not isinstance(row, dict):
                    continue
                is_long = _okx_is_long_liq(row)
                if is_long is None:
                    continue
                try:
                    size = float(row.get("sz") or 0)
                    price = float(
                        row.get("bkPx") or row.get("px") or row.get("fillPx") or 0
                    )
                except (TypeError, ValueError):
                    continue
                usd = abs(size) * ct_val * price
                if usd <= 0:
                    continue
                events.append((_parse_ts_ms(row), usd, is_long))

        return _snapshot_from_events(symbol, "okx", events)
    except Exception:
        logger.debug("OKX liquidations failed for %s", symbol, exc_info=True)
        return None


def _bybit_is_long_liq(row: dict) -> bool | None:
    """Bybit: Buy update = long liquidated; Sell = short liquidated."""
    side = str(row.get("S") or row.get("side") or "").strip().lower()
    if side == "buy":
        return True
    if side == "sell":
        return False
    return None


def _parse_bybit_liquidations(
    symbol: str, payload: dict | None
) -> LiquidationSnapshot | None:
    if not payload:
        return None
    ret = payload.get("retCode")
    if ret not in (None, 0, "0"):
        return None
    result = payload.get("result")
    rows: list = []
    if isinstance(result, dict):
        raw = result.get("list") or result.get("data") or []
        if isinstance(raw, list):
            rows = raw
    elif isinstance(payload.get("list"), list):
        rows = payload["list"]
    if not rows:
        return None

    events: list[tuple[int | None, float, bool]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        is_long = _bybit_is_long_liq(row)
        if is_long is None:
            continue
        try:
            size = float(
                row.get("v") or row.get("size") or row.get("qty") or 0
            )
            price = float(
                row.get("p")
                or row.get("price")
                or row.get("bankruptcyPrice")
                or 0
            )
        except (TypeError, ValueError):
            continue
        usd = abs(size) * price
        if usd <= 0:
            continue
        events.append((_parse_ts_ms(row), usd, is_long))
    return _snapshot_from_events(symbol, "bybit", events)


def _fetch_bybit_liquidations(symbol: str) -> LiquidationSnapshot | None:
    """Linear recent liquidations. Soft-fails CloudFront 403/451."""
    pair = f"{symbol}USDT"
    try:
        client = shared_client(timeout=5.0, name="bybit")
        for path in ("/v5/market/recent-liquidation", "/v5/market/liquidation"):
            payload = _soft_get_json(
                client,
                f"{_BYBIT_BASE}{path}",
                {"category": "linear", "symbol": pair},
            )
            snap = _parse_bybit_liquidations(symbol, payload)
            if snap is not None:
                return snap
        return None
    except Exception:
        logger.debug("Bybit liquidations failed for %s", symbol, exc_info=True)
        return None


def _fetch_coinglass(
    symbol: str,
    *,
    interval: str,
    limit: int,
    api_key: str,
) -> LiquidationSnapshot | None:
    base = settings.coinglass_base_url.rstrip("/")
    url = f"{base}/api/futures/liquidation/aggregated-history"
    params = {
        "exchange_list": settings.coinglass_exchange_list,
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    try:
        client = shared_client(timeout=5.0, name="coinglass")
        response = client.get(
            url,
            params=params,
            headers={"CG-API-KEY": api_key, "Accept": "application/json"},
        )
        if response.status_code in {401, 403, 404, 429}:
            logger.warning(
                "Coinglass liquidations HTTP %s for %s",
                response.status_code,
                symbol,
            )
            return None
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("Coinglass liquidations fetch failed for %s", symbol)
        return None

    if not isinstance(payload, dict) or str(payload.get("code")) not in {"0", "200"}:
        logger.warning("Coinglass unexpected payload for %s: %s", symbol, payload)
        return None

    rows = payload.get("data") or []
    if not isinstance(rows, list) or not rows:
        return None

    window = rows[-limit:] if len(rows) > limit else rows
    long_usd = 0.0
    short_usd = 0.0
    for row in window:
        if not isinstance(row, dict):
            continue
        long_usd += float(
            row.get("aggregated_long_liquidation_usd")
            or row.get("long_liquidation_usd")
            or 0
        )
        short_usd += float(
            row.get("aggregated_short_liquidation_usd")
            or row.get("short_liquidation_usd")
            or 0
        )

    if long_usd <= 0 and short_usd <= 0:
        return None
    return LiquidationSnapshot(
        symbol=symbol,
        long_usd=long_usd,
        short_usd=short_usd,
        interval=interval,
    )
