"""Evidence accumulation and persistence service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.evidence_engine import EvidenceEngine
from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.models.evidence_snapshot import EvidenceSnapshot
from app.schemas.evidence import EvidenceBundleSchema, EvidenceItemSchema


def _item_to_schema(item: EvidenceItem) -> EvidenceItemSchema:
    """Convert domain evidence item to API schema."""
    return EvidenceItemSchema(
        source=item.source,
        category=item.category,
        score=item.score,
        weight=item.weight,
        description=item.description,
        confidence=item.confidence,
    )


def _bundle_to_schema(bundle: EvidenceBundle) -> EvidenceBundleSchema:
    """Convert domain evidence bundle to API schema."""
    return EvidenceBundleSchema(
        id=bundle.id,
        symbol=bundle.symbol,
        timeframe=bundle.timeframe,
        total_confidence=bundle.total_confidence,
        items=[_item_to_schema(item) for item in bundle.items],
        timestamp=bundle.timestamp,
        regime=bundle.regime,
        regime_confidence=bundle.regime_confidence,
    )


def _items_to_json(items: list[EvidenceItem]) -> list[dict]:
    """Serialize evidence items for JSONB storage."""
    return [
        {
            "source": item.source,
            "category": item.category,
            "score": item.score,
            "weight": item.weight,
            "description": item.description,
            "confidence": item.confidence,
        }
        for item in items
    ]


class EvidenceService:
    """Orchestrates evidence accumulation and persistence."""

    def __init__(self, engine: EvidenceEngine | None = None) -> None:
        """Initialize with optional custom Evidence Engine (for testing)."""
        self._engine = engine or EvidenceEngine()

    def accumulate(self, symbol: str, timeframe: str = "1h") -> EvidenceBundleSchema:
        """Accumulate evidence and return API schema."""
        bundle = self._engine.accumulate(symbol, timeframe)
        return _bundle_to_schema(bundle)

    async def accumulate_and_persist(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str = "1h",
    ) -> EvidenceBundleSchema:
        """Accumulate evidence and persist an immutable snapshot."""
        bundle = self._engine.accumulate(symbol, timeframe)

        snapshot = EvidenceSnapshot(
            id=bundle.id,
            symbol=bundle.symbol,
            timeframe=bundle.timeframe,
            total_confidence=bundle.total_confidence,
            items=_items_to_json(bundle.items),
        )
        session.add(snapshot)
        await session.flush()

        return _bundle_to_schema(bundle)

    async def get_latest(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str = "1h",
    ) -> EvidenceBundleSchema | None:
        """Return the most recent persisted snapshot for an asset."""
        stmt = (
            select(EvidenceSnapshot)
            .where(
                EvidenceSnapshot.symbol == symbol.upper(),
                EvidenceSnapshot.timeframe == timeframe,
            )
            .order_by(EvidenceSnapshot.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot is None:
            return None

        return EvidenceBundleSchema(
            id=snapshot.id,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            total_confidence=snapshot.total_confidence,
            items=[EvidenceItemSchema(**item) for item in snapshot.items],
            timestamp=snapshot.created_at,
        )

    async def get_by_id(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
    ) -> EvidenceBundleSchema | None:
        """Return a persisted snapshot by ID."""
        snapshot = await session.get(EvidenceSnapshot, snapshot_id)
        if snapshot is None:
            return None

        return EvidenceBundleSchema(
            id=snapshot.id,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            total_confidence=snapshot.total_confidence,
            items=[EvidenceItemSchema(**item) for item in snapshot.items],
            timestamp=snapshot.created_at,
        )
