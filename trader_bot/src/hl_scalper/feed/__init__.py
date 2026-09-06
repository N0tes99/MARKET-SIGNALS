from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class BookLevel:
    px: float
    sz: float


@dataclass
class L2Book:
    coin: str
    bids: list[BookLevel] = field(default_factory=list)
    asks: list[BookLevel] = field(default_factory=list)
    age_s: float = 0.0

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].px if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].px if self.asks else None

    @property
    def mid(self) -> float | None:
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None or ask <= bid:
            return None
        return (bid + ask) / 2.0


class BookFeed(Protocol):
    def l2_book(self, coin: str) -> L2Book | None: ...


class HttpInfoFeed:
    """Read-only Hyperliquid /info client. Never posts to /exchange."""

    def __init__(self, *, base_url: str, timeout: float = 8.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def l2_book(self, coin: str) -> L2Book | None:
        payload = self._post({"type": "l2Book", "coin": coin.strip()})
        return parse_l2_book(coin.strip(), payload)

    def _post(self, body: dict[str, object]) -> Any:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self._base}/info", json=body)
            response.raise_for_status()
            return response.json()


def parse_l2_book(coin: str, payload: object) -> L2Book | None:
    if not isinstance(payload, dict):
        return None
    levels = payload.get("levels")
    if not isinstance(levels, list) or len(levels) < 2:
        return None
    bids_raw, asks_raw = levels[0], levels[1]
    if not isinstance(bids_raw, list) or not isinstance(asks_raw, list):
        return None
    bids = _parse_levels(bids_raw)
    asks = _parse_levels(asks_raw)
    if not bids or not asks:
        return None
    return L2Book(coin=coin, bids=bids, asks=asks)


def _parse_levels(raw: list[object]) -> list[BookLevel]:
    out: list[BookLevel] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        px = _as_float(item.get("px"))
        sz = _as_float(item.get("sz"))
        if px is None or sz is None or px <= 0 or sz <= 0:
            continue
        out.append(BookLevel(px=px, sz=sz))
    return out


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
