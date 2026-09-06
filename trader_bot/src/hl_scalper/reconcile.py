from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class VenuePosition:
    coin: str
    szi: float
    entry_px: float | None
    unrealized_pnl: float | None


@dataclass(frozen=True)
class VenueState:
    address: str
    account_value: float | None
    total_ntl_pos: float | None
    positions: tuple[VenuePosition, ...]


@dataclass(frozen=True)
class ReconcileResult:
    ok: bool
    reason: str
    venue: VenueState | None = None


class ClearinghouseClient:
    """Read-only HL user state. Never signs."""

    def __init__(self, *, info_url: str, timeout: float = 8.0) -> None:
        self._info_url = info_url.rstrip("/")
        self._timeout = timeout

    def fetch(self, address: str) -> VenueState:
        payload = self._post({"type": "clearinghouseState", "user": address})
        return parse_clearinghouse(address, payload)

    def _post(self, body: dict[str, object]) -> Any:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(self._info_url, json=body)
            response.raise_for_status()
            return response.json()


def parse_clearinghouse(address: str, payload: object) -> VenueState:
    if not isinstance(payload, dict):
        return VenueState(address=address, account_value=None, total_ntl_pos=None, positions=())
    ms = payload.get("marginSummary") if isinstance(payload.get("marginSummary"), dict) else {}
    positions: list[VenuePosition] = []
    for item in payload.get("assetPositions") or []:
        if not isinstance(item, dict):
            continue
        pos = item.get("position")
        if not isinstance(pos, dict):
            continue
        try:
            szi = float(pos.get("szi") or 0)
        except (TypeError, ValueError):
            continue
        if abs(szi) < 1e-12:
            continue
        entry = pos.get("entryPx")
        upnl = pos.get("unrealizedPnl")
        positions.append(
            VenuePosition(
                coin=str(pos.get("coin") or ""),
                szi=szi,
                entry_px=float(entry) if entry is not None else None,
                unrealized_pnl=float(upnl) if upnl is not None else None,
            )
        )
    def _f(key: str) -> float | None:
        raw = ms.get(key)
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    return VenueState(
        address=address,
        account_value=_f("accountValue"),
        total_ntl_pos=_f("totalNtlPos"),
        positions=tuple(positions),
    )


def reconcile_flat_local(*, local_open_coin: str | None, venue: VenueState) -> ReconcileResult:
    """When local bot is flat, venue must also be flat for bot coins (dust-safe)."""
    if local_open_coin is not None:
        # Holding locally — full size reconcile lands with live fills.
        return ReconcileResult(True, "local_open_skip", venue)
    if venue.positions:
        coins = ",".join(sorted({p.coin for p in venue.positions}))
        return ReconcileResult(False, f"venue_has_positions:{coins}", venue)
    return ReconcileResult(True, "flat_ok", venue)
