"""Signal store protocol and in-memory implementation."""

from collections import deque
from threading import Lock
from typing import Protocol
from uuid import UUID

from app.engines.learning_engine.types import SignalRecord

DEFAULT_MAX_PER_SYMBOL = 200


class SignalStore(Protocol):
    """Persistence interface for learning signal records."""

    def add(self, record: SignalRecord) -> None: ...

    def list_for_symbol(self, symbol: str, limit: int = 50) -> list[SignalRecord]: ...

    def list_all(self, limit: int = 100) -> list[SignalRecord]: ...

    def get(self, record_id: UUID) -> SignalRecord | None: ...

    def update(self, record: SignalRecord) -> SignalRecord | None: ...

    def count(self, symbol: str | None = None) -> int: ...

    def find_by_paper_trade_id(self, paper_trade_id: UUID) -> SignalRecord | None: ...

    def list_by_source(self, source: str, limit: int = 500) -> list[SignalRecord]: ...


class InMemorySignalStore:
    """Thread-safe ring buffer of signal records per symbol."""

    backend = "memory"

    def __init__(self, max_per_symbol: int = DEFAULT_MAX_PER_SYMBOL) -> None:
        self._max = max_per_symbol
        self._records: dict[str, deque[SignalRecord]] = {}
        self._lock = Lock()

    def add(self, record: SignalRecord) -> None:
        """Append a signal record for its symbol."""
        with self._lock:
            bucket = self._records.setdefault(record.symbol, deque(maxlen=self._max))
            bucket.append(record)

    def list_for_symbol(self, symbol: str, limit: int = 50) -> list[SignalRecord]:
        """Return recent records for a symbol, newest first."""
        with self._lock:
            bucket = self._records.get(symbol.upper(), deque())
            return list(reversed(list(bucket)))[:limit]

    def list_all(self, limit: int = 100) -> list[SignalRecord]:
        """Return recent records across all symbols, newest first."""
        with self._lock:
            combined: list[SignalRecord] = []
            for bucket in self._records.values():
                combined.extend(bucket)
            combined.sort(key=lambda r: r.timestamp, reverse=True)
            return combined[:limit]

    def get(self, record_id: UUID) -> SignalRecord | None:
        """Find a record by ID."""
        with self._lock:
            for bucket in self._records.values():
                for record in bucket:
                    if record.id == record_id:
                        return record
        return None

    def update(self, record: SignalRecord) -> SignalRecord | None:
        """Replace a record in-place by ID (used for outcome updates)."""
        with self._lock:
            for bucket in self._records.values():
                for index, existing in enumerate(bucket):
                    if existing.id == record.id:
                        bucket[index] = record
                        return record
        return None

    def count(self, symbol: str | None = None) -> int:
        """Count stored records."""
        with self._lock:
            if symbol:
                return len(self._records.get(symbol.upper(), []))
            return sum(len(b) for b in self._records.values())

    def find_by_paper_trade_id(self, paper_trade_id: UUID) -> SignalRecord | None:
        """Find the learning row linked to a paper trade."""
        with self._lock:
            for bucket in self._records.values():
                for record in bucket:
                    if record.paper_trade_id == paper_trade_id:
                        return record
        return None

    def list_by_source(self, source: str, limit: int = 500) -> list[SignalRecord]:
        """Return recent records for a provenance source."""
        with self._lock:
            matched = [
                r
                for bucket in self._records.values()
                for r in bucket
                if r.source == source
            ]
            matched.sort(key=lambda r: r.timestamp, reverse=True)
            return matched[:limit]
