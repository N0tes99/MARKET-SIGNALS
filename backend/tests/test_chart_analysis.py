"""Chart screenshot analyzer tests."""

from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from httpx import AsyncClient
from PIL import Image

from app.core.auth_deps import get_current_user
from app.engines.ai_engine.chart_analyzer import (
    DISCLAIMER,
    assemble_chart_analysis,
    attach_decision,
    normalize_symbol_hint,
)
from app.engines.ai_engine.image import ImageRejected, prepare_chart_image
from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.execution_engine.engine import ExecutionResult, ExecutionSignal
from app.engines.opportunity_engine.engine import OpportunityResult
from app.main import app
from app.models.user import User
from app.scoring.grading import TradeState
from app.services.decision_pipeline import DecisionResult


def _png(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (12, 16, 22)).save(buf, format="PNG")
    return buf.getvalue()


def _user() -> User:
    return User(
        id=uuid4(),
        email="trader@test.local",
        username="trader",
        password_hash="test",
        email_verified_at=datetime.now(UTC),
    )


def _decision(state: TradeState, signal: ExecutionSignal) -> DecisionResult:
    items = [
        EvidenceItem("t", "Trend", 72.0, 20.0, "uptrend intact"),
        EvidenceItem("mo", "Momentum", 61.0, 15.0, "thrust higher"),
    ]
    evidence = EvidenceBundle(
        symbol="BTC",
        timeframe="1h",
        items=items,
        total_confidence=64.0,
    )
    return DecisionResult(
        symbol="BTC",
        evidence=evidence,
        opportunity=OpportunityResult(
            symbol="BTC",
            opportunity_score=64.0,
            trade_grade="C",
            expected_value=0.1,
            trade_state=state,
            description="BTC: Building evidence",
        ),
        execution=ExecutionResult(
            symbol="BTC",
            signal=signal,
            confidence=64.0,
            description="watch",
        ),
        risk=None,
        trade_state=state,
        summary="BTC — watch the tape",
    )


def test_prepare_rejects_empty() -> None:
    with pytest.raises(ImageRejected, match="Empty"):
        prepare_chart_image(b"", "image/png")


def test_prepare_rejects_non_image() -> None:
    with pytest.raises(ImageRejected, match="readable"):
        prepare_chart_image(b"not-an-image", "image/png")


def test_prepare_rejects_tiny() -> None:
    with pytest.raises(ImageRejected, match="too small"):
        prepare_chart_image(_png(16, 16), "image/png")


def test_prepare_rejects_bad_mime() -> None:
    with pytest.raises(ImageRejected, match="PNG"):
        prepare_chart_image(_png(64, 64), "application/pdf")


def test_prepare_accepts_png() -> None:
    prepared = prepare_chart_image(_png(64, 48), "image/png")
    assert prepared.mime == "image/png"
    assert prepared.width == 64
    assert prepared.height == 48
    assert prepared.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_normalize_symbol_hint_strips_quote() -> None:
    assert normalize_symbol_hint("btcusdt") == "BTC"
    assert normalize_symbol_hint("ETH/USD") == "ETH"
    assert normalize_symbol_hint("NVDA") == "NVDA"
    assert normalize_symbol_hint("none") is None


def test_assemble_defaults_to_no_trade() -> None:
    result = assemble_chart_analysis({}, source="local")
    assert result.source == "local"
    assert result.disclaimer == DISCLAIMER
    assert result.positions[0].bias == "no_trade"
    assert result.positions[0].execution_hint == "WAIT"
    assert result.engine_grounding is None


def test_assemble_clamps_execute_when_engine_is_wait() -> None:
    parsed = {
        "symbol": "BTCUSDT",
        "trend": "bullish",
        "structure": "Higher highs into range high.",
        "thesis": "Breakout watch, not a chase.",
        "positions": [
            {
                "bias": "long",
                "setup_name": "Range break",
                "thesis": "Wait for a hold above the high.",
                "entry_zone": "above 64,200",
                "invalidation": "back inside the range",
                "targets": ["65,400"],
                "risk_notes": "False break common.",
                "execution_hint": "EXECUTE",
                "confidence": 71,
            }
        ],
        "conflicts": [],
        "image_quality": "good",
    }
    result = assemble_chart_analysis(
        parsed,
        source="openai",
        decision=_decision(TradeState.WATCH, ExecutionSignal.WAIT),
    )
    assert result.reading.symbol == "BTC"
    assert result.positions[0].execution_hint == "WATCH"
    assert result.engine_grounding is not None
    assert result.engine_grounding.symbol == "BTC"
    assert result.engine_grounding.alignment in {"agrees", "conflicts", "incomplete"}


def test_ignore_state_forces_wait() -> None:
    parsed = {
        "symbol": "BTC",
        "trend": "bullish",
        "positions": [
            {
                "bias": "long",
                "setup_name": "Chase",
                "thesis": "Looks extended.",
                "execution_hint": "EXECUTE",
                "confidence": 80,
            }
        ],
    }
    result = assemble_chart_analysis(
        parsed,
        source="gemini",
        decision=_decision(TradeState.IGNORE, ExecutionSignal.WAIT),
    )
    assert result.positions[0].execution_hint == "WAIT"
    assert result.engine_grounding is not None
    assert result.engine_grounding.alignment == "conflicts"


def test_attach_decision_adds_grounding() -> None:
    result = assemble_chart_analysis(
        {
            "symbol": "BTC",
            "trend": "range",
            "thesis": "Chop.",
            "positions": [
                {
                    "bias": "no_trade",
                    "setup_name": "Stand aside",
                    "thesis": "No location.",
                    "execution_hint": "WAIT",
                    "confidence": 30,
                }
            ],
        },
        source="openai",
    )
    grounded = attach_decision(result, _decision(TradeState.WATCH, ExecutionSignal.WATCH))
    assert grounded.engine_grounding is not None
    assert grounded.engine_grounding.asset_path == "/assets/BTC"


@pytest.mark.asyncio
async def test_chart_analysis_requires_login(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/chart-analysis",
        files={"file": ("chart.png", _png(64, 64), "image/png")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chart_analysis_rejects_tiny_image(client: AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = _user
    try:
        response = await client.post(
            "/api/v1/chart-analysis",
            files={"file": ("chart.png", _png(16, 16), "image/png")},
        )
        assert response.status_code == 400
        assert "too small" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_chart_analysis_mocked_success(client: AsyncClient) -> None:
    from app.core.service_dependencies import get_chart_analyzer
    from app.engines.ai_engine.chart_analyzer import ChartAnalyzer
    from app.engines.ai_engine.image import PreparedImage
    from app.schemas.chart_analysis import ChartAnalysisSchema

    class _Fake(ChartAnalyzer):
        def analyze(
            self,
            image: PreparedImage,
            *,
            note: str = "",
            symbol_hint: str = "",
            decision: DecisionResult | None = None,
        ) -> ChartAnalysisSchema:
            assert image.width >= 32
            return assemble_chart_analysis(
                {
                    "symbol": "BTC",
                    "trend": "range",
                    "structure": "Range high rejected.",
                    "thesis": "Wait for a location.",
                    "positions": [
                        {
                            "bias": "no_trade",
                            "setup_name": "No location",
                            "thesis": note or "Stand aside.",
                            "execution_hint": "WAIT",
                            "confidence": 28,
                        }
                    ],
                    "image_quality": "good",
                },
                source="openai",
                decision=decision,
            )

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_chart_analyzer] = _Fake
    try:
        response = await client.post(
            "/api/v1/chart-analysis",
            files={"file": ("chart.png", _png(80, 60), "image/png")},
            data={"note": "Thinking fade", "symbol_hint": "BTC"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["reading"]["symbol"] == "BTC"
        assert body["positions"][0]["bias"] == "no_trade"
        assert body["engine_grounding"]["symbol"] == "BTC"
        assert "decision support" in body["disclaimer"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_chart_analyzer, None)


@pytest.mark.asyncio
async def test_chart_analysis_local_fallback_with_symbol(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.engines.ai_engine import engine as ai_mod

    monkeypatch.setattr(ai_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "groq_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "gemini_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "local_llm_base_url", "")
    app.dependency_overrides[get_current_user] = _user
    try:
        response = await client.post(
            "/api/v1/chart-analysis",
            data={"symbol_hint": "BTC", "note": "range high"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "local"
        assert body["reading"]["symbol"] == "BTC"
        assert body["engine_grounding"]["symbol"] == "BTC"
        assert body["positions"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_chart_analysis_requires_file_or_symbol(client: AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = _user
    try:
        response = await client.post("/api/v1/chart-analysis")
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_chart_analysis_status_reports_local_llm(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.engines.ai_engine import engine as ai_mod

    monkeypatch.setattr(ai_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "groq_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "gemini_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "local_llm_base_url", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(ai_mod.settings, "local_llm_model", "qwen2.5-vl-7b-instruct")
    app.dependency_overrides[get_current_user] = _user
    try:
        response = await client.get("/api/v1/chart-analysis/status")
        assert response.status_code == 200
        body = response.json()
        assert body["vision"] is True
        assert body["source"] == "local_llm"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_openai_compat_base_url_appends_v1() -> None:
    from app.engines.ai_engine.engine import openai_compat_base_url

    assert openai_compat_base_url("http://127.0.0.1:1234") == "http://127.0.0.1:1234/v1"
    assert openai_compat_base_url("http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234/v1"


def test_local_llm_backend_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.engines.ai_engine import engine as ai_mod

    monkeypatch.setattr(ai_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "groq_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "gemini_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "local_llm_base_url", "http://192.168.1.20:1234")
    monkeypatch.setattr(ai_mod.settings, "local_llm_model", "qwen2.5-vl-7b-instruct")
    backend = ai_mod.get_llm_backend()
    assert backend is not None
    _client, model, source = backend
    assert source == "local_llm"
    assert model == "qwen2.5-vl-7b-instruct"
