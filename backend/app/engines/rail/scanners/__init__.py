"""Run HL-native scanners. Empty book is a valid sit-out."""

from __future__ import annotations

import logging

from app.engines.rail.adapters.hyperliquid_info import HyperliquidInfo, LiveHyperliquidInfo
from app.engines.rail.scanners.book import scan_books
from app.engines.rail.scanners.funding import scan_funding
from app.engines.rail.scanners.outcome import scan_outcomes
from app.engines.rail.types import OpportunityEnvelope, SealedInstrument

logger = logging.getLogger(__name__)


class HyperliquidRailScanner:
    """Phase B identify path. Does not place orders."""

    def __init__(self, info: HyperliquidInfo | None = None) -> None:
        self._info = info or LiveHyperliquidInfo()

    def scan(self) -> list[tuple[OpportunityEnvelope, SealedInstrument]]:
        try:
            rows = [
                *scan_funding(self._info),
                *scan_books(self._info),
                *scan_outcomes(self._info),
            ]
        except Exception:
            logger.warning("rail hyperliquid scan failed", exc_info=True)
            return []
        seen: set[str] = set()
        unique: list[tuple[OpportunityEnvelope, SealedInstrument]] = []
        for envelope, sealed in rows:
            if envelope.envelope_id in seen:
                continue
            seen.add(envelope.envelope_id)
            unique.append((envelope, sealed))
        return unique
