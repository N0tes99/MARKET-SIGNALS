"""Pytest configuration and shared fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.service_dependencies import (
    get_decision_pipeline,
    get_evidence_service,
    get_learning_engine,
    get_test_decision_pipeline,
    get_test_evidence_service,
    get_test_learning_engine,
    get_test_weight_optimizer,
    get_weight_optimizer,
)
from app.engines.learning_engine import LearningEngine
from app.main import app
from app.services.decision_pipeline import DecisionPipelineService
from app.services.evidence_service import EvidenceService


@pytest.fixture
def evidence_service() -> EvidenceService:
    """Provide an evidence service backed by mock market data."""
    return get_test_evidence_service()


@pytest.fixture
def decision_pipeline() -> DecisionPipelineService:
    """Provide a decision pipeline backed by mock market data."""
    return get_test_decision_pipeline()


@pytest.fixture
def learning_engine() -> LearningEngine:
    """Provide a fresh learning engine for tests."""
    return get_test_learning_engine()


@pytest.fixture
async def client(
    evidence_service: EvidenceService,
    decision_pipeline: DecisionPipelineService,
    learning_engine: LearningEngine,
) -> AsyncClient:
    """Provide an async HTTP client with mock services injected."""
    app.dependency_overrides[get_evidence_service] = lambda: evidence_service
    app.dependency_overrides[get_decision_pipeline] = lambda: decision_pipeline
    app.dependency_overrides[get_learning_engine] = lambda: learning_engine
    app.dependency_overrides[get_weight_optimizer] = get_test_weight_optimizer

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
