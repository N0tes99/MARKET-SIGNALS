"""Read-only broker adapter protocol (v1 — no execution)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ReadOnlyBrokerAdapter(Protocol):
    """Minimal read-only surface shared by live broker mirrors.

    Execution (place/cancel) belongs on a separate interface and must never
    be mixed into the read-only path.
    """

    def configured(self) -> bool:
        """True when credentials are present."""
        ...

    def get_mirror(self) -> object:
        """Fetch a snapshot suitable for dashboard display."""
        ...
