"""Episodic record types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EpisodicRecord:
    """One stored cortex tick snapshot."""

    tick_id: str
    as_of: datetime
    payload: dict[str, Any]
