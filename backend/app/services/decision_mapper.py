"""Decision pipeline API mapping helpers."""

from app.market_data.freshness import freshness_tracker
from app.schemas.decision import DecisionSchema, ExecutionSchema, RiskSchema
from app.schemas.evidence import EvidenceBundleSchema, EvidenceItemSchema
from app.services.decision_pipeline import DecisionResult


def decision_to_schema(result: DecisionResult) -> DecisionSchema:
    """Convert a pipeline result to an API schema."""
    evidence = result.evidence
    evidence_schema = EvidenceBundleSchema(
        id=evidence.id,
        symbol=evidence.symbol,
        timeframe=evidence.timeframe,
        total_confidence=evidence.total_confidence,
        items=[
            EvidenceItemSchema(
                source=item.source,
                category=item.category,
                score=item.score,
                weight=item.weight,
                description=item.description,
                confidence=item.confidence,
            )
            for item in evidence.items
        ],
        timestamp=evidence.timestamp,
        regime=evidence.regime,
        regime_confidence=evidence.regime_confidence,
    )

    risk_schema = None
    if result.risk:
        risk_schema = RiskSchema(
            position_size=result.risk.position_size,
            stop_loss=result.risk.stop_loss,
            take_profit=result.risk.take_profit,
            max_drawdown=result.risk.max_drawdown,
            risk_percent=result.risk.risk_percent,
            risk_reward_ratio=result.risk.risk_reward_ratio,
            score=result.risk.score,
            description=result.risk.description,
        )

    snap = freshness_tracker.status(result.symbol)
    return DecisionSchema(
        symbol=result.symbol,
        evidence=evidence_schema,
        opportunity_score=result.opportunity.opportunity_score,
        trade_grade=result.opportunity.trade_grade,
        expected_value=result.opportunity.expected_value,
        trade_state=result.trade_state.value,
        execution=ExecutionSchema(
            signal=result.execution.signal.value,
            confidence=result.execution.confidence,
            description=result.execution.description,
        ),
        risk=risk_schema,
        summary=result.summary,
        data_degraded=snap.degraded,
        data_age_seconds=snap.age_seconds,
        data_stale_reason=snap.reason,
    )
