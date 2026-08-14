"""Coinglass derivatives helpers — aggregated liquidation history."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.utils.http_client import shared_client
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)


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
    """Fetch recent aggregated coin liquidations; None if no key or failure."""
    key = (settings.coinglass_api_key or "").strip()
    if not key:
        return None

    normalized = symbol.upper()
    cache_key = f"{normalized}:{interval}:{limit}"

    def _load() -> LiquidationSnapshot | None:
        base = settings.coinglass_base_url.rstrip("/")
        url = f"{base}/api/futures/liquidation/aggregated-history"
        params = {
            "exchange_list": settings.coinglass_exchange_list,
            "symbol": normalized,
            "interval": interval,
            "limit": limit,
        }
        try:
            client = shared_client(timeout=5.0, name="coinglass")
            response = client.get(
                url,
                params=params,
                headers={"CG-API-KEY": key, "Accept": "application/json"},
            )
            if response.status_code in {401, 403, 404, 429}:
                logger.warning(
                    "Coinglass liquidations HTTP %s for %s",
                    response.status_code,
                    normalized,
                )
                return None
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logger.exception("Coinglass liquidations fetch failed for %s", normalized)
            return None

        if not isinstance(payload, dict) or str(payload.get("code")) not in {"0", "200"}:
            logger.warning("Coinglass unexpected payload for %s: %s", normalized, payload)
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

        return LiquidationSnapshot(
            symbol=normalized,
            long_usd=long_usd,
            short_usd=short_usd,
            interval=interval,
        )

    return _LIQ_CACHE.get_or_set(cache_key, _load)
