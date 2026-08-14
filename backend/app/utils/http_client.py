"""Process-local keep-alive httpx clients.

Same request/response payloads as one-shot ``httpx.Client`` usage — only the
TCP/TLS handshake is reused. Safe to share across threads for ``.get`` / ``.post``.
"""

from __future__ import annotations

from contextlib import suppress
from threading import Lock

import httpx

_LOCK = Lock()
_CLIENTS: dict[tuple[object, ...], httpx.Client] = {}

_DEFAULT_LIMITS = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=40,
    keepalive_expiry=30.0,
)


def shared_client(
    *,
    timeout: float,
    name: str = "default",
    headers: dict[str, str] | None = None,
) -> httpx.Client:
    """Return a cached Client keyed by name, timeout, and optional default headers."""
    header_key = tuple(sorted((headers or {}).items()))
    key: tuple[object, ...] = (name, timeout, header_key)
    with _LOCK:
        client = _CLIENTS.get(key)
        if client is None or client.is_closed:
            client = httpx.Client(
                timeout=timeout,
                headers=headers,
                limits=_DEFAULT_LIMITS,
                follow_redirects=True,
            )
            _CLIENTS[key] = client
        return client


def reset_shared_clients() -> None:
    """Close and drop cached clients (tests / process teardown)."""
    with _LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
    for client in clients:
        with suppress(Exception):
            client.close()
