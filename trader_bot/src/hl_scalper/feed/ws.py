from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Iterable

from hl_scalper.feed import BookFeed, HttpInfoFeed, L2Book, parse_l2_book

logger = logging.getLogger(__name__)

DEFAULT_WS_URL = "wss://api.hyperliquid.xyz/ws"


class HybridBookFeed:
    """HTTP poll fallback + optional WS cache for fresher books.

    `l2_book()` is sync (loop-friendly). WS updates land in a thread-safe cache.
    """

    def __init__(
        self,
        *,
        info_url: str,
        coins: tuple[str, ...],
        ws_url: str = DEFAULT_WS_URL,
        use_ws: bool = True,
        max_book_age_s: float = 2.0,
    ) -> None:
        self._http = HttpInfoFeed(base_url=info_url)
        self._coins = coins
        self._ws_url = ws_url
        self._use_ws = use_ws
        self._max_book_age_s = max_book_age_s
        self._lock = threading.Lock()
        self._books: dict[str, tuple[L2Book, float]] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if use_ws:
            self._thread = threading.Thread(target=self._run_ws, name="hl-ws-books", daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._stop.set()

    def l2_book(self, coin: str) -> L2Book | None:
        key = coin.strip().upper()
        now = time.monotonic()
        with self._lock:
            cached = self._books.get(key)
        if cached is not None:
            book, ts = cached
            age = now - ts
            if age <= self._max_book_age_s:
                book.age_s = age
                return book
        # HTTP fallback / warm cache
        book = self._http.l2_book(key)
        if book is None:
            return None
        book.age_s = 0.0
        with self._lock:
            self._books[key] = (book, time.monotonic())
        return book

    def _run_ws(self) -> None:
        while not self._stop.is_set():
            try:
                asyncio.run(self._ws_loop())
            except Exception:  # noqa: BLE001
                logger.warning("hl ws loop crashed; reconnecting", exc_info=True)
            if self._stop.wait(2.0):
                return

    async def _ws_loop(self) -> None:
        import websockets

        async with websockets.connect(self._ws_url, open_timeout=10, ping_interval=20) as ws:
            for coin in self._coins:
                await ws.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "subscription": {"type": "l2Book", "coin": coin},
                        }
                    )
                )
            while not self._stop.is_set():
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                msg = json.loads(raw)
                if msg.get("channel") != "l2Book":
                    continue
                data = msg.get("data")
                if not isinstance(data, dict):
                    continue
                coin = str(data.get("coin") or "").upper()
                book = parse_l2_book(coin, data)
                if book is None:
                    continue
                book.age_s = 0.0
                with self._lock:
                    self._books[coin] = (book, time.monotonic())


def build_feed(
    *,
    info_url: str,
    coins: Iterable[str],
    use_ws: bool,
    max_ws_book_age_s: float = 2.0,
) -> BookFeed:
    coin_t = tuple(c.strip().upper() for c in coins if c.strip())
    if use_ws:
        return HybridBookFeed(
            info_url=info_url,
            coins=coin_t,
            use_ws=True,
            max_book_age_s=max_ws_book_age_s,
        )
    return HttpInfoFeed(base_url=info_url)
