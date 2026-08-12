"""Universe scanner + EARLY / IGNITION / RUNNING list builders."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from app.engines.runner_engine.config import RunnerConfig, default_runner_config
from app.engines.runner_engine.engine import RunnerEngine
from app.engines.runner_engine.types import RunnerCandidate, WatchlistBucket
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_FEED_MAX_WORKERS = 6


class RunnerScanner:
    """Scan configured seed universe into ranked RunnerCandidates."""

    def __init__(
        self,
        engine: RunnerEngine | None = None,
        config: RunnerConfig | None = None,
    ) -> None:
        self.config = config or default_runner_config()
        self.engine = engine or RunnerEngine(config=self.config)
        self._cache: TTLCache[list[RunnerCandidate]] = TTLCache(
            ttl_seconds=self.config.scan_cache_ttl_seconds
        )

    @property
    def universe(self) -> tuple[str, ...]:
        return self.config.seed_universe

    def evaluate(self, symbol: str) -> RunnerCandidate:
        """Evaluate a single symbol (bypasses feed cache)."""
        return self.engine.evaluate(symbol)

    def scan(
        self,
        symbols: Sequence[str] | None = None,
        *,
        watchlist: WatchlistBucket | None = None,
        min_runner_score: float = 0.0,
        stage: str | None = None,
        use_cache: bool = True,
    ) -> list[RunnerCandidate]:
        """Scan symbols and optionally filter by list / score / stage."""
        universe = tuple(s.upper() for s in (symbols if symbols is not None else self.universe))
        cache_key = ",".join(universe)

        def _load() -> list[RunnerCandidate]:
            return self._scan_universe(universe)

        candidates = (
            self._cache.get_or_set(cache_key, _load) if use_cache else _load()
        )

        filtered = [
            c
            for c in candidates
            if c.scores.runner_score >= min_runner_score
            and (watchlist is None or c.watchlist == watchlist)
            and (stage is None or c.stage == stage)
        ]
        filtered.sort(key=lambda c: c.scores.runner_score, reverse=True)
        return filtered

    def _scan_universe(self, universe: Sequence[str]) -> list[RunnerCandidate]:
        results: list[RunnerCandidate] = []
        if not universe:
            return results

        workers = min(_FEED_MAX_WORKERS, len(universe))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.engine.evaluate, sym): sym for sym in universe}
            for fut in as_completed(futures):
                sym = futures[fut]
                try:
                    results.append(fut.result())
                except Exception:
                    logger.exception("Runner scan failed for %s", sym)
        results.sort(key=lambda c: c.scores.runner_score, reverse=True)
        logger.info(
            "runner_scan complete symbols=%d as_of=%s",
            len(results),
            datetime.now(UTC).isoformat(),
        )
        return results

    def lists(
        self,
        symbols: Sequence[str] | None = None,
    ) -> dict[str, list[RunnerCandidate]]:
        """Return EARLY / IGNITION / RUNNING buckets."""
        all_cands = self.scan(symbols, use_cache=True)
        return {
            "early": [c for c in all_cands if c.watchlist == "early"],
            "ignition": [c for c in all_cands if c.watchlist == "ignition"],
            "running": [c for c in all_cands if c.watchlist == "running"],
        }
