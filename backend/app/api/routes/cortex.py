"""Cortex brain API — working memory, tick, episodic history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.rate_limit import limit_expensive
from app.core.service_dependencies import get_cortex_orchestrator
from app.cortex.orchestrator import CortexOrchestrator
from app.cortex.types import WorkingMemory
from app.schemas.cortex import (
    CortexHealthSchema,
    CortexHistoryResponse,
    CortexSemanticResponse,
    CortexTickResponse,
    EpisodicRecordSchema,
    SemanticStatSchema,
    SpecialistOpinionSchema,
    SymbolContextSchema,
    WorkingMemorySchema,
)

router = APIRouter()


def _expansion_summary(ctx) -> dict | None:
    exp = ctx.expansion
    if exp is None:
        return None
    return {
        "state": exp.state.value,
        "direction_bias": exp.direction_bias,
        "up_score": exp.up_score,
        "down_score": exp.down_score,
        "net_score": exp.net_score,
        "trigger_active": exp.trigger_active,
        "compression_score": exp.compression.score,
        "squeeze_score": exp.squeeze.score,
        "factors": list(exp.factors[:5]),
    }


def _memory_to_schema(memory: WorkingMemory, *, digest: str = "") -> WorkingMemorySchema:
    symbols = [
        SymbolContextSchema(
            symbol=ctx.symbol,
            opinions=[
                SpecialistOpinionSchema(
                    specialist=o.specialist,
                    score=o.score,
                    direction=o.direction,
                    factors=list(o.factors),
                    conflicts=list(o.conflicts),
                    metadata=dict(o.metadata),
                )
                for o in ctx.opinions
            ],
            alert_level=ctx.alert_level,
            synthesis_notes=list(ctx.synthesis_notes),
            prior_state=ctx.prior_state.value if ctx.prior_state else None,
            expansion_summary=_expansion_summary(ctx),
        )
        for ctx in memory.symbols.values()
    ]
    return WorkingMemorySchema(
        tick_id=memory.tick_id,
        as_of=memory.as_of,
        universe=list(memory.universe),
        symbols=symbols,
        global_opinions=[
            SpecialistOpinionSchema(
                specialist=o.specialist,
                score=o.score,
                direction=o.direction,
                factors=list(o.factors),
                conflicts=list(o.conflicts),
                metadata=dict(o.metadata),
            )
            for o in memory.global_opinions
        ],
        notes=list(memory.notes),
        phase=memory.phase,
        primed=memory.primed_symbols(),
        triggering=memory.triggering_symbols(),
        digest=digest,
    )


@router.get("", response_model=WorkingMemorySchema)
def get_cortex_state(
    orchestrator: CortexOrchestrator = Depends(get_cortex_orchestrator),
    run_if_empty: bool = Query(True, description="Run a tick when no prior memory exists"),
) -> WorkingMemorySchema:
    """Latest working memory (runs one tick if empty)."""
    memory = orchestrator.last_memory
    if memory is None and run_if_empty:
        memory = orchestrator.tick()
    if memory is None:
        raise HTTPException(status_code=404, detail="No cortex memory — POST /cortex/tick first")
    return _memory_to_schema(memory, digest=orchestrator.digest())


@router.post("/tick", response_model=CortexTickResponse)
def post_cortex_tick(
    request: Request,
    orchestrator: CortexOrchestrator = Depends(get_cortex_orchestrator),
) -> CortexTickResponse:
    """Run one cortex heartbeat now."""
    limit_expensive(request)
    memory = orchestrator.tick(persist=True)
    return CortexTickResponse(
        memory=_memory_to_schema(memory, digest=orchestrator.digest()),
        persisted=True,
    )


@router.get("/history", response_model=CortexHistoryResponse)
def get_cortex_history(
    orchestrator: CortexOrchestrator = Depends(get_cortex_orchestrator),
    limit: int = Query(20, ge=1, le=100),
) -> CortexHistoryResponse:
    """Recent episodic cortex snapshots."""
    records = orchestrator.episodic.history(limit=limit)
    return CortexHistoryResponse(
        records=[
            EpisodicRecordSchema(
                tick_id=r.tick_id,
                as_of=r.as_of,
                payload=r.payload,
            )
            for r in records
        ],
        count=len(records),
    )


@router.get("/semantic", response_model=CortexSemanticResponse)
def get_cortex_semantic(
    orchestrator: CortexOrchestrator = Depends(get_cortex_orchestrator),
) -> CortexSemanticResponse:
    """Lead-time and calibration stats from episodic history."""
    stats = orchestrator.semantic.all_stats()
    lead = next((s for s in stats if s.metric == "lead_time"), None)
    return CortexSemanticResponse(
        stats=[
            SemanticStatSchema(
                metric=s.metric,
                signal=s.signal,
                score_bucket=s.score_bucket,
                sample_count=s.sample_count,
                median_hours=s.median_hours,
                hit_rate=s.hit_rate,
                payload=dict(s.payload),
            )
            for s in stats
        ],
        lead_time_hours=lead.median_hours if lead else None,
        sample_count=lead.sample_count if lead else 0,
    )


@router.get("/health", response_model=CortexHealthSchema)
def get_cortex_health(
    orchestrator: CortexOrchestrator = Depends(get_cortex_orchestrator),
) -> CortexHealthSchema:
    """Episodic freshness and store backend."""
    from app.cortex.lifecycle import assess_health

    latest = orchestrator.episodic.latest()
    backend = getattr(orchestrator.episodic, "backend", "memory")
    health = assess_health(
        last_tick_at=latest.as_of if latest else None,
        ticks_recorded=orchestrator.episodic.count(),
        backend=str(backend),
    )
    return CortexHealthSchema(
        last_tick_at=health.last_tick_at,
        ticks_recorded=health.ticks_recorded,
        healthy=health.healthy,
        backend=health.backend,
        notes=list(health.notes),
    )
