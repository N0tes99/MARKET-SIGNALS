"""Decision pipeline — Evidence → Opportunity → Execution → Risk."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.engines.evidence_engine import EvidenceEngine
from app.engines.evidence_engine.types import EvidenceBundle
from app.engines.execution_engine import ExecutionEngine, ExecutionResult, ExecutionSignal
from app.engines.opportunity_engine import OpportunityEngine, OpportunityResult
from app.engines.risk_engine import RiskAssessment, RiskEngine
from app.market_data.service import MarketDataService
from app.scoring.grading import TradeState
from app.utils.ttl_cache import TTLCache

# Collapse duplicate asset-page / concurrent evaluate hits
_EVAL_CACHE: TTLCache[DecisionResult] = TTLCache(ttl_seconds=90.0)

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


class DecisionPipelineService:
    """Orchestrates the full evidence-to-decision pipeline."""

    RISK_VETO_THRESHOLD = 40.0

    def __init__(
        self,
        market_data: MarketDataService | None = None,
        evidence_engine: EvidenceEngine | None = None,
        opportunity_engine: OpportunityEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        """Initialize pipeline with injectable engines."""
        self._market_data = market_data or MarketDataService()
        self._evidence = evidence_engine or EvidenceEngine(market_data=self._market_data)
        self._opportunity = opportunity_engine or OpportunityEngine()
        self._execution = execution_engine or ExecutionEngine()
        self._risk = risk_engine or RiskEngine(self._market_data)

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
        execution = self._execution.evaluate(normalized, evidence, opportunity)
        trade_state = self._resolve_trade_state(opportunity, execution, risk)

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
        # Prefetch shared benchmarks at the same limit engines use (cache-key match)
        self._market_data.warm(["SPY", "QQQ", "BTC"], timeframe=timeframe, limit=200)
        try:
            self._market_data.get_ticker("^VIX")
        except Exception:
            pass

        # One CoinGecko batch for all alts (avoids per-symbol cold HTTP in on-chain)
        try:
            from app.engines.onchain_engine.engine import warm_coingecko_activity

            warm_coingecko_activity()
        except Exception:
            pass

        workers = min(len(symbols), 10)
        if len(symbols) <= 1:
            results = [self.evaluate(symbol, timeframe) for symbol in symbols]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(lambda s: self.evaluate(s, timeframe), symbols))
        return sorted(results, key=lambda d: d.opportunity.opportunity_score, reverse=True)

    def _resolve_trade_state(
        self,
        opportunity: OpportunityResult,
        execution: ExecutionResult,
        risk: RiskAssessment | None,
    ) -> TradeState:
        """Determine final trade state with risk veto."""
        if opportunity.opportunity_score < OpportunityEngine.WATCH_THRESHOLD:
            return TradeState.IGNORE

        if execution.signal == ExecutionSignal.EXECUTE:
            if risk and risk.score >= self.RISK_VETO_THRESHOLD:
                return TradeState.EXECUTE
            return TradeState.WATCH  # risk veto

        if (
            execution.signal == ExecutionSignal.WATCH
            or opportunity.opportunity_score >= OpportunityEngine.WATCH_THRESHOLD
        ):
            return TradeState.WATCH

        return TradeState.IGNORE

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
