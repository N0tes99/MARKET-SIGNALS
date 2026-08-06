"""Decision pipeline — Evidence → Opportunity → Execution → Risk."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Protocol

from app.engines.evidence_engine import EvidenceEngine
from app.engines.evidence_engine.types import EvidenceBundle
from app.engines.execution_engine import ExecutionEngine, ExecutionResult, ExecutionSignal
from app.engines.opportunity_engine import OpportunityEngine, OpportunityResult
from app.engines.risk_engine import RiskAssessment, RiskEngine
from app.market_data.service import MarketDataService
from app.scoring.grading import TradeState
from app.utils.ttl_cache import TTLCache


@dataclass
class DecisionResult:
    """Complete decision output for a single asset."""

    symbol: str
    evidence: EvidenceBundle
    opportunity: OpportunityResult
    execution: ExecutionResult
    risk: RiskAssessment | None
    trade_state: TradeState
    summary: str


class LearningSupport(Protocol):
    """Optional learning hooks used by the pipeline (avoids hard import cycle)."""

    def blend_expected_value(
        self,
        symbol: str,
        formula_ev: float,
        risk_reward_ratio: float,
        *,
        min_samples: int = 3,
    ) -> float: ...

    def open_manage_context(self, symbol: str) -> dict[str, bool]: ...


# Collapse duplicate asset-page / concurrent evaluate hits
_EVAL_CACHE: TTLCache[DecisionResult] = TTLCache(ttl_seconds=90.0)


class DecisionPipelineService:
    """Orchestrates the full evidence-to-decision pipeline."""

    # Stricter than ExecutionEngine's timing risk floor (40) so veto can still fire
    RISK_VETO_THRESHOLD = 48.0
    RISK_VETO_MIN_RR = 1.35

    def __init__(
        self,
        market_data: MarketDataService | None = None,
        evidence_engine: EvidenceEngine | None = None,
        opportunity_engine: OpportunityEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        risk_engine: RiskEngine | None = None,
        learning_engine: LearningSupport | None = None,
    ) -> None:
        """Initialize pipeline with injectable engines."""
        self._market_data = market_data or MarketDataService()
        self._evidence = evidence_engine or EvidenceEngine(market_data=self._market_data)
        self._opportunity = opportunity_engine or OpportunityEngine()
        self._execution = execution_engine or ExecutionEngine()
        self._risk = risk_engine or RiskEngine(self._market_data)
        self._learning = learning_engine

    def evaluate(self, symbol: str, timeframe: str = "1h") -> DecisionResult:
        """Run the full decision pipeline for an asset (cached ~90s)."""
        normalized = symbol.upper()
        cache_key = f"{normalized}:{timeframe}"
        return _EVAL_CACHE.get_or_set(
            cache_key,
            lambda: self._evaluate_uncached(normalized, timeframe),
        )

    def _evaluate_uncached(self, normalized: str, timeframe: str) -> DecisionResult:
        """Compute a fresh decision without reading the evaluate cache."""
        evidence = self._evidence.accumulate(normalized, timeframe)
        risk = self._risk.assess(normalized, timeframe=timeframe)
        rr = risk.risk_reward_ratio if risk else 1.5

        opportunity = self._opportunity.evaluate(normalized, evidence, rr)
        opportunity = self._apply_learning_ev(normalized, opportunity, rr)
        execution = self._execution.evaluate(normalized, evidence, opportunity)
        trade_state = self._resolve_trade_state(
            normalized,
            opportunity,
            execution,
            risk,
            evidence,
        )

        summary = self._build_summary(normalized, opportunity, execution, trade_state, risk)

        return DecisionResult(
            symbol=normalized,
            evidence=evidence,
            opportunity=opportunity,
            execution=execution,
            risk=risk,
            trade_state=trade_state,
            summary=summary,
        )

    def rank_all(
        self,
        symbols: list[str],
        timeframe: str = "1h",
    ) -> list[DecisionResult]:
        """Evaluate and rank all symbols by opportunity score."""
        # Prefetch all listed symbols (+ shared benches) at limit=200 so trend /
        # correlation / sector collectors hit the same OHLCV cache key.
        warm_symbols = list(dict.fromkeys([*symbols, "SPY", "QQQ", "BTC"]))
        self._market_data.warm(warm_symbols, timeframe=timeframe, limit=200)
        with suppress(Exception):
            self._market_data.get_ticker("^VIX")

        # One CoinGecko batch for all alts (avoids per-symbol cold HTTP in on-chain)
        try:
            from app.engines.onchain_engine.engine import warm_coingecko_activity

            warm_coingecko_activity()
        except Exception:
            pass

        # Free-tier Render OOMs / 502s with 18 concurrent evaluates; 8 stays stable.
        workers = min(len(symbols), 8)
        if len(symbols) <= 1:
            results = [self.evaluate(symbol, timeframe) for symbol in symbols]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(lambda s: self.evaluate(s, timeframe), symbols))
        return sorted(results, key=lambda d: d.opportunity.opportunity_score, reverse=True)

    def _apply_learning_ev(
        self,
        symbol: str,
        opportunity: OpportunityResult,
        risk_reward_ratio: float,
    ) -> OpportunityResult:
        """Blend opportunity EV with learning history when enough samples exist."""
        if self._learning is None:
            return opportunity
        blended = self._learning.blend_expected_value(
            symbol,
            opportunity.expected_value,
            risk_reward_ratio,
        )
        if blended == opportunity.expected_value:
            return opportunity
        return replace(opportunity, expected_value=blended)

    def _risk_approved(self, risk: RiskAssessment | None) -> bool:
        """True when risk quality and R:R clear the veto gates."""
        if risk is None:
            return False
        return (
            risk.score >= self.RISK_VETO_THRESHOLD
            and risk.risk_reward_ratio >= self.RISK_VETO_MIN_RR
        )

    def _resolve_trade_state(
        self,
        symbol: str,
        opportunity: OpportunityResult,
        execution: ExecutionResult,
        risk: RiskAssessment | None,
        evidence: EvidenceBundle,
    ) -> TradeState:
        """Resolve final trade_state after opportunity + execution + risk.

        Rules (pragmatic lifecycle without a broker adapter):
        - IGNORE when opportunity is below the watch threshold.
        - EXECUTE when timing is EXECUTE and risk clears quality + min R:R gates;
          otherwise timing EXECUTE is risk-vetoed down to WATCH.
        - WATCH when timing is WATCH or opportunity alone warrants monitoring.
        - MANAGE when learning has an unresolved EXECUTE/MANAGE signal for the
          symbol and conditions still support a hold (timing EXECUTE/WATCH,
          opportunity still watchable, evidence not collapsed, risk not failed
          after prior execute territory).
        - EXIT when an open manage context degrades (opportunity below watch,
          execution WAIT, risk fails after manage territory) OR learning's most
          recent signal was closed with an outcome while base state is not a
          fresh EXECUTE.
        Opportunity never emits EXECUTE itself; ExecutionEngine owns timing and
        this resolver owns the surfaced trade_state.
        """
        below_watch = opportunity.opportunity_score < OpportunityEngine.WATCH_THRESHOLD

        base = TradeState.IGNORE
        if not below_watch and execution.signal == ExecutionSignal.EXECUTE:
            base = TradeState.EXECUTE if self._risk_approved(risk) else TradeState.WATCH
        elif (
            not below_watch
            and (
                execution.signal == ExecutionSignal.WATCH
                or opportunity.opportunity_score >= OpportunityEngine.WATCH_THRESHOLD
            )
        ):
            base = TradeState.WATCH

        return self._apply_lifecycle(symbol, base, opportunity, execution, risk, evidence)

    def _has_open_active(self, symbol: str) -> bool:
        if self._learning is None:
            return False
        return bool(self._learning.open_manage_context(symbol).get("has_open_active"))

    def _apply_lifecycle(
        self,
        symbol: str,
        base: TradeState,
        opportunity: OpportunityResult,
        execution: ExecutionResult,
        risk: RiskAssessment | None,
        evidence: EvidenceBundle,
    ) -> TradeState:
        if self._learning is None:
            return base

        ctx = self._learning.open_manage_context(symbol)
        has_open = bool(ctx.get("has_open_active"))
        recently_closed = bool(ctx.get("recently_closed"))

        evidence_collapsed = evidence.total_confidence < OpportunityEngine.WATCH_THRESHOLD
        degraded = (
            opportunity.opportunity_score < OpportunityEngine.WATCH_THRESHOLD
            or execution.signal == ExecutionSignal.WAIT
            or evidence_collapsed
            or (
                has_open
                and not self._risk_approved(risk)
                and base != TradeState.EXECUTE
            )
        )

        if has_open:
            if degraded:
                return TradeState.EXIT
            if base in {TradeState.EXECUTE, TradeState.WATCH} and not evidence_collapsed:
                return TradeState.MANAGE
            if base == TradeState.IGNORE:
                return TradeState.EXIT

        if recently_closed and base != TradeState.EXECUTE and degraded:
            return TradeState.EXIT

        return base

    def _build_summary(
        self,
        symbol: str,
        opportunity: OpportunityResult,
        execution: ExecutionResult,
        trade_state: TradeState,
        risk: RiskAssessment | None,
    ) -> str:
        """Build a one-line human-readable decision summary."""
        parts = [
            f"{symbol}: {trade_state.value}",
            f"grade {opportunity.trade_grade}",
            f"score {opportunity.opportunity_score:.0f}%",
            f"signal {execution.signal.value}",
        ]
        if risk:
            parts.append(f"R:R {risk.risk_reward_ratio:.1f}:1")
        return " — ".join(parts)
