"""Read-only Hyperliquid /info client. Never posts to /exchange."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings
from app.utils.http_client import shared_client
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

HL_PERP_UNIVERSE: tuple[str, ...] = ("BTC", "ETH", "SOL", "HYPE")
_TIMEOUT = 8.0
_CTX_TTL = 30.0
_BOOK_TTL = 15.0
_OUTCOME_TTL = 45.0


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class BookLevel:
    px: float
    sz: float


@dataclass
class L2Book:
    coin: str
    bids: list[BookLevel] = field(default_factory=list)
    asks: list[BookLevel] = field(default_factory=list)

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].px if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].px if self.asks else None


@dataclass(frozen=True)
class PerpContext:
    coin: str
    funding: float | None
    premium: float | None
    mark_px: float | None
    oracle_px: float | None
    open_interest: float | None
    mid_px: float | None


@dataclass(frozen=True)
class OutcomeSpec:
    outcome_id: int
    name: str
    description: str


class HyperliquidInfo(Protocol):
    """Read-only surface used by Rail scanners. Tests inject fakes."""

    def perp_contexts(self, coins: tuple[str, ...] = HL_PERP_UNIVERSE) -> list[PerpContext]:
        ...

    def l2_book(self, coin: str) -> L2Book | None:
        ...

    def outcomes(self, limit: int = 3) -> list[OutcomeSpec]:
        ...


class LiveHyperliquidInfo:
    """POST https://api.hyperliquid.xyz/info — public, no auth."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self._base = (base_url or settings.hyperliquid_info_url).rstrip("/")
        self._ctx_cache: TTLCache[list[PerpContext]] = TTLCache(ttl_seconds=_CTX_TTL)
        self._book_cache: TTLCache[L2Book] = TTLCache(ttl_seconds=_BOOK_TTL)
        self._outcome_cache: TTLCache[list[OutcomeSpec]] = TTLCache(ttl_seconds=_OUTCOME_TTL)

    def perp_contexts(self, coins: tuple[str, ...] = HL_PERP_UNIVERSE) -> list[PerpContext]:
        wanted = {coin.upper() for coin in coins}

        def _load() -> list[PerpContext]:
            payload = self._post({"type": "metaAndAssetCtxs"})
            return _parse_perp_contexts(payload, wanted)

        try:
            return list(self._ctx_cache.get_or_set("ctxs:" + ",".join(sorted(wanted)), _load))
        except Exception:
            logger.warning("hyperliquid metaAndAssetCtxs failed", exc_info=True)
            return []

    def l2_book(self, coin: str) -> L2Book | None:
        key = coin.strip()

        def _load() -> L2Book:
            payload = self._post({"type": "l2Book", "coin": key})
            # Empty book is cached so sit-out does not re-hit /info every snapshot.
            return _parse_l2_book(key, payload) or L2Book(coin=key)

        try:
            book = self._book_cache.get_or_set(f"book:{key}", _load)
        except Exception:
            logger.warning("hyperliquid l2Book failed coin=%s", key, exc_info=True)
            return None
        if not book.bids or not book.asks:
            return None
        return book

    def outcomes(self, limit: int = 3) -> list[OutcomeSpec]:
        def _load() -> list[OutcomeSpec]:
            payload = self._post({"type": "outcomeMeta"})
            return _parse_outcomes(payload)[: max(0, limit)]

        try:
            return list(self._outcome_cache.get_or_set(f"outcomes:{limit}", _load))
        except Exception:
            logger.warning("hyperliquid outcomeMeta failed", exc_info=True)
            return []

    def _post(self, body: dict[str, object]) -> Any:
        client = shared_client(timeout=_TIMEOUT, name="hyperliquid-info")
        response = client.post(f"{self._base}/info", json=body)
        response.raise_for_status()
        return response.json()


def _parse_perp_contexts(payload: object, wanted: set[str]) -> list[PerpContext]:
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    meta, ctxs = payload[0], payload[1]
    if not isinstance(meta, dict) or not isinstance(ctxs, list):
        return []
    universe = meta.get("universe")
    if not isinstance(universe, list):
        return []
    out: list[PerpContext] = []
    for idx, item in enumerate(universe):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").upper()
        if name not in wanted:
            continue
        ctx = ctxs[idx] if idx < len(ctxs) and isinstance(ctxs[idx], dict) else {}
        out.append(
            PerpContext(
                coin=name,
                funding=_as_float(ctx.get("funding")),
                premium=_as_float(ctx.get("premium")),
                mark_px=_as_float(ctx.get("markPx")),
                oracle_px=_as_float(ctx.get("oraclePx")),
                open_interest=_as_float(ctx.get("openInterest")),
                mid_px=_as_float(ctx.get("midPx")),
            )
        )
    return out


def _parse_levels(raw: object) -> list[BookLevel]:
    if not isinstance(raw, list):
        return []
    levels: list[BookLevel] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        px = _as_float(row.get("px"))
        sz = _as_float(row.get("sz"))
        if px is None or sz is None or px <= 0 or sz <= 0:
            continue
        levels.append(BookLevel(px=px, sz=sz))
    return levels


def _parse_l2_book(coin: str, payload: object) -> L2Book | None:
    if not isinstance(payload, dict):
        return None
    levels = payload.get("levels")
    if not isinstance(levels, list) or len(levels) < 2:
        return None
    book = L2Book(
        coin=coin,
        bids=_parse_levels(levels[0]),
        asks=_parse_levels(levels[1]),
    )
    if not book.bids or not book.asks:
        return None
    return book


def _parse_outcomes(payload: object) -> list[OutcomeSpec]:
    rows: list[object]
    if isinstance(payload, dict):
        raw = payload.get("outcomes")
        rows = raw if isinstance(raw, list) else []
    elif isinstance(payload, list):
        rows = payload
    else:
        return []
    out: list[OutcomeSpec] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            outcome_id = int(item.get("outcome"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        name = str(item.get("name") or "")
        description = str(item.get("description") or "")
        out.append(OutcomeSpec(outcome_id=outcome_id, name=name, description=description))
    return out
