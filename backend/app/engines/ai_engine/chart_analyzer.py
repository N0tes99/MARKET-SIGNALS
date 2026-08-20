"""Chart screenshot analyzer — vision LLM reads structure; engines still decide."""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.engines.ai_engine.engine import get_llm_backend
from app.engines.ai_engine.image import PreparedImage
from app.market_data.symbols import is_tracked
from app.schemas.chart_analysis import (
    ChartAnalysisSchema,
    ChartReadingSchema,
    EngineGroundingSchema,
    PositionIdeaSchema,
)
from app.services.decision_pipeline import DecisionResult

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Chart analysis is decision support, not a recommendation or order. "
    "Engines decide; the analyst explains. A screenshot can be stale, cropped, "
    "or missing context — sitting out is a valid outcome."
)

_ALLOWED_TRENDS = frozenset({"bullish", "bearish", "range", "unclear"})
_ALLOWED_BIAS = frozenset({"long", "short", "no_trade"})
_ALLOWED_EXEC = frozenset({"WAIT", "WATCH", "EXECUTE"})
_ALLOWED_QUALITY = frozenset({"good", "partial", "unreadable"})
_ALLOWED_CLASSES = frozenset(
    {"crypto", "stock", "etf", "futures", "options", "unknown"}
)

_SYSTEM_PROMPT = (
    "You are Signal Engine's Chart Analyst. You read trading screenshots "
    "(candlestick charts, DOM, options chains, PnL, order tickets) and explain "
    "what is visible. You NEVER give buy/sell commands. Sitting out is a "
    "first-class outcome. Label everything as analysis, not a recommendation. "
    "Protect capital first. If the image is not a market screenshot, say so "
    "and return a single no_trade position with WAIT. "
    "If live desk evidence is provided, treat engines as the decision layer: "
    "the chart is visual context. Do not upgrade engine WAIT/WATCH/IGNORE to "
    "EXECUTE. You may still describe a setup the chart shows, but "
    "execution_hint must stay WAIT or WATCH unless engines are already EXECUTE "
    "and the chart agrees. Always include at least one position. Prefer "
    "explicit invalidation and a no_trade alternative when structure is messy. "
    "Respond in JSON with keys: symbol (string or null), asset_class "
    "(crypto|stock|etf|futures|options|unknown), timeframe (string or null), "
    "chart_type, last_price (number or null), trend "
    "(bullish|bearish|range|unclear), structure (string), key_levels "
    "(array of strings), indicators_visible (array of strings), observations "
    "(array of short bullets), thesis (2-4 sentences), positions (array of "
    "objects with bias long|short|no_trade, setup_name, thesis, entry_zone, "
    "invalidation, targets array, risk_notes, execution_hint WAIT|WATCH|EXECUTE, "
    "confidence 0-100), conflicts (array of strings), image_quality "
    "(good|partial|unreadable)."
)

_SYMBOL_STRIP = ("USDT", "USDC", "BUSD", "PERP")
_SYMBOL_CLEAN = re.compile(r"[^A-Z0-9.=]")


class VisionUnavailable(RuntimeError):
    """No OpenAI/Gemini key configured for vision."""


class ChartAnalyzer:
    """Reads a chart screenshot and returns explainable position navigation."""

    def analyze(
        self,
        image: PreparedImage,
        *,
        note: str = "",
        symbol_hint: str = "",
        decision: DecisionResult | None = None,
    ) -> ChartAnalysisSchema:
        backend = get_llm_backend()
        if backend is None:
            raise VisionUnavailable(
                "Vision analysis needs OPENAI_API_KEY or GEMINI_API_KEY"
            )
        client, model, source = backend
        payload = _user_payload(note=note, symbol_hint=symbol_hint, decision=decision)
        data_url = (
            f"data:{image.mime};base64,{base64.b64encode(image.data).decode('ascii')}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": payload},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1600,
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Chart analyzer returned non-JSON; using empty parse")
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        return assemble_chart_analysis(parsed, source=source, decision=decision)


def attach_decision(
    result: ChartAnalysisSchema,
    decision: DecisionResult,
) -> ChartAnalysisSchema:
    """Re-clamp positions and attach live desk grounding after a late symbol match."""
    reading = result.reading
    payload = {
        "symbol": reading.symbol,
        "asset_class": reading.asset_class,
        "timeframe": reading.timeframe,
        "chart_type": reading.chart_type,
        "last_price": reading.last_price,
        "trend": reading.trend,
        "structure": reading.structure,
        "key_levels": reading.key_levels,
        "indicators_visible": reading.indicators_visible,
        "observations": reading.observations,
        "image_quality": reading.image_quality,
        "thesis": result.thesis,
        "positions": [item.model_dump() for item in result.positions],
        "conflicts": result.conflicts,
    }
    return assemble_chart_analysis(payload, source=result.source, decision=decision)


def assemble_chart_analysis(
    parsed: dict[str, Any],
    *,
    source: str,
    decision: DecisionResult | None = None,
) -> ChartAnalysisSchema:
    """Normalize LLM JSON (and optional engine snapshot) into the API schema."""
    symbol = _normalize_symbol(parsed.get("symbol"))
    reading = ChartReadingSchema(
        symbol=symbol,
        asset_class=_one_of(parsed.get("asset_class"), _ALLOWED_CLASSES, "unknown"),
        timeframe=_optional_str(parsed.get("timeframe"), 32),
        chart_type=_optional_str(parsed.get("chart_type"), 48) or "unknown",
        last_price=_optional_float(parsed.get("last_price")),
        trend=_one_of(parsed.get("trend"), _ALLOWED_TRENDS, "unclear"),
        structure=_optional_str(parsed.get("structure"), 800) or "Structure not readable.",
        key_levels=_str_list(parsed.get("key_levels"), 8, 120),
        indicators_visible=_str_list(parsed.get("indicators_visible"), 8, 80),
        observations=_str_list(parsed.get("observations"), 8, 200),
        image_quality=_one_of(parsed.get("image_quality"), _ALLOWED_QUALITY, "partial"),
    )
    engine_signal = decision.execution.signal.value if decision else None
    trade_state = decision.trade_state.value if decision else None
    positions = [
        _coerce_position(item, engine_signal=engine_signal, trade_state=trade_state)
        for item in _as_list(parsed.get("positions"))
    ]
    positions = [p for p in positions if p is not None]
    if not positions:
        positions = [
            PositionIdeaSchema(
                bias="no_trade",
                setup_name="Insufficient chart evidence",
                thesis="The screenshot does not support a high-conviction setup.",
                entry_zone=None,
                invalidation=None,
                targets=[],
                risk_notes="Wait for a cleaner location or a tracked desk decision.",
                execution_hint="WAIT",
                confidence=20.0,
                chart_derived=True,
            )
        ]
    grounding = _engine_grounding(decision, reading) if decision else None
    conflicts = _str_list(parsed.get("conflicts"), 6, 220)
    if grounding and grounding.alignment == "conflicts":
        for note in grounding.alignment_notes:
            if note not in conflicts:
                conflicts.append(note)
    thesis = _optional_str(parsed.get("thesis"), 1200) or (
        f"{reading.symbol or 'This screenshot'} looks {reading.trend}. "
        f"{reading.structure}"
    )
    return ChartAnalysisSchema(
        reading=reading,
        thesis=thesis,
        positions=positions[:4],
        conflicts=conflicts[:8],
        engine_grounding=grounding,
        source=source,
        disclaimer=DISCLAIMER,
        generated_at=datetime.now(UTC),
    )


def normalize_symbol_hint(raw: str | None) -> str | None:
    """Public helper for optional form `symbol_hint`."""
    return _normalize_symbol(raw)


def _engine_grounding(
    decision: DecisionResult,
    reading: ChartReadingSchema,
) -> EngineGroundingSchema:
    notes: list[str] = []
    engine_exec = decision.execution.signal.value
    chart_trend = reading.trend
    alignment = "incomplete"
    if chart_trend == "bullish" and decision.trade_state in {"EXECUTE", "WATCH"}:
        alignment = "agrees"
    elif chart_trend == "bearish" and decision.trade_state in {"IGNORE"}:
        alignment = "agrees"
        notes.append("Bearish chart with desk IGNORE — capital stays protected.")
    elif chart_trend in {"bullish", "bearish"} and decision.trade_state == "IGNORE":
        alignment = "conflicts"
        notes.append(
            f"Chart looks {chart_trend} while desk state is IGNORE — do not chase."
        )
    elif chart_trend == "bullish" and engine_exec == "WAIT":
        alignment = "conflicts"
        notes.append("Chart looks bid while execution engine is WAIT.")
    elif chart_trend == "range":
        alignment = "incomplete"
        notes.append("Range on the screenshot — wait for a location, not a prediction.")
    else:
        alignment = "incomplete"

    return EngineGroundingSchema(
        symbol=decision.symbol,
        tracked=is_tracked(decision.symbol),
        trade_state=decision.trade_state.value,
        trade_grade=decision.opportunity.trade_grade,
        execution_signal=engine_exec,
        opportunity_score=decision.opportunity.opportunity_score,
        summary=decision.summary,
        alignment=alignment,
        alignment_notes=notes,
        asset_path=f"/assets/{decision.symbol}" if is_tracked(decision.symbol) else None,
    )


def _coerce_position(
    raw: Any,
    *,
    engine_signal: str | None,
    trade_state: str | None,
) -> PositionIdeaSchema | None:
    if not isinstance(raw, dict):
        return None
    bias = _one_of(raw.get("bias"), _ALLOWED_BIAS, "no_trade")
    hint = str(raw.get("execution_hint") or "WATCH").upper()
    if hint not in _ALLOWED_EXEC:
        hint = "WATCH"
    if bias == "no_trade":
        hint = "WAIT"
    hint = _clamp_execution(hint, engine_signal=engine_signal, trade_state=trade_state)
    confidence = _optional_float(raw.get("confidence"))
    if confidence is None:
        confidence = 40.0
    confidence = max(0.0, min(100.0, confidence))
    setup = _optional_str(raw.get("setup_name"), 80) or "Unnamed setup"
    thesis = _optional_str(raw.get("thesis"), 600) or "No thesis provided."
    return PositionIdeaSchema(
        bias=bias,
        setup_name=setup,
        thesis=thesis,
        entry_zone=_optional_str(raw.get("entry_zone"), 160),
        invalidation=_optional_str(raw.get("invalidation"), 160),
        targets=_str_list(raw.get("targets"), 4, 80),
        risk_notes=_optional_str(raw.get("risk_notes"), 300) or "",
        execution_hint=hint,
        confidence=confidence,
        chart_derived=True,
    )


def _clamp_execution(
    hint: str,
    *,
    engine_signal: str | None,
    trade_state: str | None,
) -> str:
    """Chart may describe a setup; it cannot upgrade engine WAIT/IGNORE to EXECUTE."""
    if hint != "EXECUTE":
        return hint
    if trade_state == "IGNORE":
        return "WAIT"
    if engine_signal in {"WAIT", "WATCH"} or trade_state == "WATCH":
        return "WATCH"
    return hint


def _user_payload(
    *,
    note: str,
    symbol_hint: str,
    decision: DecisionResult | None,
) -> str:
    parts = [
        "Analyze this trading screenshot. Extract structure, levels, and "
        "possible positions with a thesis and execution timing "
        "(WAIT / WATCH / EXECUTE). Include invalidation."
    ]
    if symbol_hint:
        parts.append(f"User symbol hint: {symbol_hint}.")
    if note:
        parts.append(f"User note: {note[:500]}")
    if decision is not None:
        parts.append(
            "Live desk evidence (engines decide; do not override):\n"
            + json.dumps(
                {
                    "symbol": decision.symbol,
                    "trade_state": decision.trade_state.value,
                    "trade_grade": decision.opportunity.trade_grade,
                    "execution_signal": decision.execution.signal.value,
                    "opportunity_score": decision.opportunity.opportunity_score,
                    "summary": decision.summary,
                    "risk": (
                        {
                            "stop_loss": decision.risk.stop_loss,
                            "take_profit": decision.risk.take_profit,
                            "risk_reward_ratio": decision.risk.risk_reward_ratio,
                        }
                        if decision.risk
                        else None
                    ),
                },
                indent=2,
            )
        )
    return "\n\n".join(parts)


def _normalize_symbol(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).upper().strip()
    if not text or text in {"NULL", "NONE", "UNKNOWN", "N/A"}:
        return None
    text = text.replace(" ", "")
    if "/" in text:
        text = text.split("/", 1)[0]
    text = _SYMBOL_CLEAN.sub("", text)
    for suffix in _SYMBOL_STRIP:
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            text = text[: -len(suffix)]
    if text.endswith("USD") and len(text) > 4:
        candidate = text[:-3]
        if is_tracked(candidate):
            text = candidate
    if not text or len(text) > 16:
        return None
    return text


def _optional_str(value: Any, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none"}:
        return None
    return text[:max_len]


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _one_of(value: Any, allowed: frozenset[str], default: str) -> str:
    text = str(value or "").strip().lower()
    if text in allowed:
        return text
    upper = text.upper()
    if upper in allowed:
        return upper
    return default


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _str_list(value: Any, limit: int, max_len: int) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        text = str(item).strip()
        if text:
            out.append(text[:max_len])
        if len(out) >= limit:
            break
    return out
