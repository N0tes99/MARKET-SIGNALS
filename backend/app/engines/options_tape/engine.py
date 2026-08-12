"""Aggressive options tape: volume screen, then balanced long/short hunts."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from uuid import uuid4

from app.engines.opportunity_engine.equity_options.option_chain import (
    RawOptionRow,
    fetch_yahoo_option_chain,
)
from app.engines.opportunity_engine.equity_options.option_selector import score_option_candidates
from app.engines.opportunity_engine.equity_options.plan_builder import build_execution_plan
from app.engines.opportunity_engine.equity_options.types import DirectionBias, EquitySetupType
from app.engines.options_tape.flow import score_option_flow
from app.engines.options_tape.screen import score_tape
from app.engines.options_tape.types import (
    Heat,
    TapeBoard,
    TapeHunt,
    TapeScreen,
    screen_to_momentum,
)
from app.engines.options_tape.universe import default_tape_universe, merge_extra_symbols
from app.market_data.service import MarketDataService
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_BOARD_CACHE: TTLCache[TapeBoard] = TTLCache(ttl_seconds=180.0)
_SCREEN_WORKERS = 8
_CHAIN_WORKERS = 4
_SIDE_FLOOR = 52.0

OptionChainFetcher = Callable[[str], list[RawOptionRow]]


def _vol_score(rel_vol: float) -> float:
    """Map relative volume onto 0–100. 1.0×≈42, 1.5×≈58, 2.5×≈78, 4×≈92."""
    return clamp_score(28.0 + rel_vol * 20.0, 20, 96)


def _heat(rel_vol: float, hunt: float) -> Heat:
    if rel_vol >= 2.2 or hunt >= 72:
        return "hot"
    return "warm"


def _setup_type(screen: TapeScreen, direction: DirectionBias) -> EquitySetupType:
    if direction == "long" and screen.dist_20d_high_pct <= 3.5 and screen.relative_volume >= 1.2:
        return "breakout_convexity"
    if direction == "short" and screen.dist_20d_low_pct <= 3.5 and screen.relative_volume >= 1.2:
        return "breakout_convexity"
    return "momentum_continuation"


def _pick_side(screen: TapeScreen) -> DirectionBias | None:
    """One ticker, one side — stronger tape wins so the board can stay balanced."""
    if not screen.standout:
        return None
    if screen.long_score >= screen.short_score + 3 and screen.long_score >= _SIDE_FLOOR:
        return "long"
    if screen.short_score >= screen.long_score + 3 and screen.short_score >= _SIDE_FLOOR:
        return "short"
    if screen.long_score >= _SIDE_FLOOR and screen.long_score >= screen.short_score:
        return "long"
    if screen.short_score >= _SIDE_FLOOR:
        return "short"
    return None


class OptionsTapeScanner:
    """Volume-first aggressive options hunter. Hot hunts can feed paper after confirm."""

    def __init__(
        self,
        market_data: MarketDataService,
        *,
        chain_fetcher: OptionChainFetcher | None = None,
    ) -> None:
        self._md = market_data
        self._fetch_chain = chain_fetcher or fetch_yahoo_option_chain

    def scan_board(
        self,
        *,
        extra_symbols: Sequence[str] | None = None,
        per_side: int = 5,
        min_rel_vol: float = 1.15,
    ) -> TapeBoard:
        per_side = max(1, min(int(per_side), 8))
        universe = merge_extra_symbols(default_tape_universe(), extra_symbols)
        cache_key = f"{','.join(universe)}|{per_side}|{min_rel_vol:.2f}"
        cached = _BOARD_CACHE.get(cache_key)
        if cached is not None:
            return cached

        screens = self._screen_universe(universe)
        longs_q, shorts_q = self._queue_sides(screens, per_side, min_rel_vol)
        needed = {s.symbol for s in (*longs_q, *shorts_q)}
        chains = self._fetch_chains(needed)

        longs = [
            hunt
            for screen in longs_q
            if (hunt := self._build_hunt(screen, "long", chains.get(screen.symbol, [])))
        ]
        shorts = [
            hunt
            for screen in shorts_q
            if (hunt := self._build_hunt(screen, "short", chains.get(screen.symbol, [])))
        ]
        longs.sort(key=lambda h: h.hunt_score, reverse=True)
        shorts.sort(key=lambda h: h.hunt_score, reverse=True)

        board = TapeBoard(
            longs=longs[:per_side],
            shorts=shorts[:per_side],
            symbols_scanned=len(universe),
            symbols_optioned=len(needed),
            per_side=per_side,
            scanned_at=datetime.now(UTC),
        )
        _BOARD_CACHE.set(cache_key, board)
        return board

    def _screen_universe(self, universe: tuple[str, ...]) -> list[TapeScreen]:
        out: list[TapeScreen] = []

        def _one(symbol: str) -> TapeScreen | None:
            frame = self._md.safe_get_ohlcv(symbol, "1d", limit=90)
            return score_tape(symbol, frame)

        with ThreadPoolExecutor(max_workers=_SCREEN_WORKERS) as pool:
            futures = {pool.submit(_one, symbol): symbol for symbol in universe}
            for fut in as_completed(futures):
                symbol = futures[fut]
                try:
                    screen = fut.result()
                except Exception:
                    logger.warning("Tape screen failed for %s", symbol, exc_info=True)
                    continue
                if screen is not None:
                    out.append(screen)
        return out

    def _queue_sides(
        self,
        screens: list[TapeScreen],
        per_side: int,
        min_rel_vol: float,
    ) -> tuple[list[TapeScreen], list[TapeScreen]]:
        longs: list[TapeScreen] = []
        shorts: list[TapeScreen] = []
        for screen in screens:
            if screen.relative_volume < min_rel_vol and not screen.standout:
                continue
            side = _pick_side(screen)
            if side == "long":
                longs.append(screen)
            elif side == "short":
                shorts.append(screen)
        longs.sort(key=lambda s: (s.relative_volume, s.long_score), reverse=True)
        shorts.sort(key=lambda s: (s.relative_volume, s.short_score), reverse=True)
        take = per_side + 2  # a couple extras in case a chain is empty
        return longs[:take], shorts[:take]

    def _fetch_chains(self, symbols: set[str]) -> dict[str, list[RawOptionRow]]:
        found: dict[str, list[RawOptionRow]] = {}
        if not symbols:
            return found

        def _one(symbol: str) -> tuple[str, list[RawOptionRow]]:
            try:
                return symbol, self._fetch_chain(symbol)
            except Exception:
                logger.warning("Option chain failed for %s", symbol, exc_info=True)
                return symbol, []

        with ThreadPoolExecutor(max_workers=_CHAIN_WORKERS) as pool:
            futures = [pool.submit(_one, symbol) for symbol in symbols]
            for fut in as_completed(futures):
                symbol, rows = fut.result()
                found[symbol] = rows
        return found

    def _build_hunt(
        self,
        screen: TapeScreen,
        direction: DirectionBias,
        rows: list[RawOptionRow],
    ) -> TapeHunt | None:
        flow = score_option_flow(rows)
        candidates = score_option_candidates(screen.symbol, screen.price, direction, rows)
        selected = candidates[0] if candidates else None
        if selected is None:
            return None

        tape_side = screen.long_score if direction == "long" else screen.short_score
        flow_side = flow.long_flow if direction == "long" else flow.short_flow
        unusual = flow.max_call_vol_oi if direction == "long" else flow.max_put_vol_oi
        hunt = clamp_score(
            _vol_score(screen.relative_volume) * 0.40
            + tape_side * 0.25
            + flow_side * 0.20
            + selected.overall_score * 0.15
        )
        factors = [
            *screen.factors,
            *flow.factors,
            f"{direction.upper()} {selected.right} {selected.strike:g} {selected.expiry}",
        ]
        conflicts = [*screen.conflicts, *flow.conflicts]
        if direction == "long" and flow.put_call_vol >= 1.5:
            conflicts.append("Puts leading while hunting calls — crowd is hedging")
        if direction == "short" and flow.put_call_vol <= 0.6:
            conflicts.append("Calls leading while hunting puts — crowd is still bid")

        plan = build_execution_plan(
            screen.symbol,
            direction,
            screen_to_momentum(screen),
            selected,
            setup_type=_setup_type(screen, direction),
        )
        return TapeHunt(
            id=f"{screen.symbol.lower()}-{direction}-{uuid4().hex[:8]}",
            symbol=screen.symbol,
            direction=direction,
            heat=_heat(screen.relative_volume, hunt),
            hunt_score=hunt,
            relative_volume=screen.relative_volume,
            range_expansion=screen.range_expansion,
            ret_5d_pct=screen.ret_5d_pct,
            ret_20d_pct=screen.ret_20d_pct,
            put_call_vol=flow.put_call_vol,
            option_volume=flow.total_option_volume,
            unusual_vol_oi=round(unusual, 3),
            factors=factors[:8],
            conflicts=conflicts[:6],
            selected_option=selected,
            option_candidates=candidates[:3],
            execution_plan=plan,
        )
