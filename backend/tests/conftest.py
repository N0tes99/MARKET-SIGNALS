"""Pytest configuration and shared fixtures."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_deps import require_admin_user
from app.core.rate_limit import reset_rate_limits
from app.core.service_dependencies import (
    get_decision_pipeline,
    get_evidence_service,
    get_learning_engine,
    get_test_evidence_service,
    get_test_market_data_service,
    get_test_weight_optimizer,
    get_weight_optimizer,
)
from app.engines.learning_engine import LearningEngine
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.paper_agent.agent import PaperAgent
from app.main import app
from app.models.user import User
from app.services.decision_pipeline import DecisionPipelineService
from app.services.evidence_service import EvidenceService


@pytest.fixture(autouse=True)
def _reset_auth_rate_limits() -> None:
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def _unpause_paper_sources_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tick tests open crypto_setup; production pause stays in paper_policy."""
    monkeypatch.setattr(
        "app.engines.paper_agent.paper_policy.PAUSED_NEW_OPEN_SOURCES",
        frozenset(),
    )


@pytest.fixture(autouse=True)
def _silence_cme_paper_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing paper ticks must not hit Yahoo CME quotes."""
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas",
        lambda *a, **k: [],
    )


def ok_paper_pipeline():
    """Stub decision pipeline that clears the paper confirm gates."""

    class _Pipe:
        def evaluate(self, symbol, timeframe="1h"):  # noqa: ANN001
            return SimpleNamespace(
                opportunity=SimpleNamespace(
                    trade_grade="A",
                    expected_value=0.4,
                    trade_state="WATCH",
                ),
                trade_state="WATCH",
                risk=SimpleNamespace(
                    score=62.0,
                    risk_reward_ratio=2.0,
                    stop_loss=96.0,
                    take_profit=108.0,
                ),
            )

    return _Pipe()


@pytest.fixture(autouse=True)
def _stable_paper_confirm_feeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep paper ticks off live F&G / earnings HTTP in unit tests."""
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (45, "Neutral"),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.earnings_soon",
        lambda symbol, within_days=2.0: False,
    )


@pytest.fixture(autouse=True)
def _inject_ok_paper_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paper constructors that omit pipeline used to open with confirm:off."""
    original = PaperAgent.__init__

    def _init(self, *args, **kwargs):  # noqa: ANN001
        if kwargs.get("pipeline") is None:
            kwargs["pipeline"] = ok_paper_pipeline()
        original(self, *args, **kwargs)

    monkeypatch.setattr(PaperAgent, "__init__", _init)


@pytest.fixture
def evidence_service() -> EvidenceService:
    """Provide an evidence service backed by mock market data."""
    return get_test_evidence_service()


@pytest.fixture
def learning_engine() -> LearningEngine:
    """Provide a fresh learning engine for tests."""
    return LearningEngine(store=InMemorySignalStore())


@pytest.fixture
def decision_pipeline(learning_engine: LearningEngine) -> DecisionPipelineService:
    """Provide a decision pipeline sharing the test learning store."""
    md = get_test_market_data_service()
    return DecisionPipelineService(market_data=md, learning_engine=learning_engine)


def _test_admin_user() -> User:
    """Synthetic admin for outcome-log / paper-reset endpoints in API tests."""
    return User(
        id=uuid4(),
        email="admin@test.local",
        username="Admin",
        password_hash="test",
        email_verified_at=datetime.now(UTC),
    )


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
    app.dependency_overrides[require_admin_user] = _test_admin_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
