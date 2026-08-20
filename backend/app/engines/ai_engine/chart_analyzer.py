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
from app.market_data.symbols import is_tracked, resolve_asset_class
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
    "You are Signal Engine's Chart Analyst. On every screenshot you MUST "
    "automatically scan for the best possible setups — the user does not type "
    "a prompt. Read candlesticks, levels, volume, indicators, DOM, or tickets. "
    "Rank locations. Return 2–3 positions ordered best-first: (1) the highest "
    "quality long OR short location the chart actually shows, (2) the opposite "
    "side if a real location exists, (3) a no_trade / WAIT stand-aside. "
    "Scan for: range fade, breakout/hold, pullback to VWAP/EMA/level, "
    "liquidity sweep / stop run, failed auction, compression → expansion. "
    "Every setup needs entry_zone, invalidation, targets, and WAIT/WATCH/EXECUTE. "
    "You NEVER give buy/sell commands. Sitting out is first-class. Label "
    "analysis, not a recommendation. Protect capital first. If the image is "
    "not a market screenshot or structure is messy, a single no_trade WAIT. "
    "If live desk evidence is provided, engines decide: do not upgrade engine "
    "WAIT/WATCH/IGNORE to EXECUTE. You may still describe the chart setup. "
    "Respond in JSON with keys: symbol (string or null), asset_class "
    "(crypto|stock|etf|futures|options|unknown), timeframe (string or null), "
    "chart_type, last_price (number or null), trend "
    "(bullish|bearish|range|unclear), structure (string), key_levels "
    "(array of strings), indicators_visible (array of strings), observations "
    "(array of short bullets), thesis (2-4 sentences naming the best setup), "
    "positions (array, best first, objects with bias long|short|no_trade, "
    "setup_name, thesis, entry_zone, invalidation, targets array, risk_notes, "
    "execution_hint WAIT|WATCH|EXECUTE, confidence 0-100), conflicts "
    "(array of strings), image_quality (good|partial|unreadable)."
)

_SYMBOL_STRIP = ("USDT", "USDC", "BUSD", "PERP")
_SYMBOL_CLEAN = re.compile(r"[^A-Z0-9.=]")


class VisionUnavailable(RuntimeError):
    """No vision backend configured (local desk fallback should be used instead)."""


class ChartAnalyzer:
    """Reads a chart screenshot and returns explainable position navigation."""

    def analyze(
        self,
        image: PreparedImage | None = None,
        *,
        note: str = "",
        symbol_hint: str = "",
        decision: DecisionResult | None = None,
    ) -> ChartAnalysisSchema:
        backend = get_llm_backend()
        if backend is None or image is None:
            return analyze_locally(
                note=note,
                symbol_hint=symbol_hint,
                decision=decision,
            )
        try:
            return self._analyze_with_vision(
                image,
                backend=backend,
                note=note,
                symbol_hint=symbol_hint,
                decision=decision,
            )
        except Exception:
            logger.exception("Vision analysis failed; using local desk fallback")
            return analyze_locally(
                note=note,
                symbol_hint=symbol_hint,
                decision=decision,
            )

    def _analyze_with_vision(
        self,
        image: PreparedImage,
        *,
        backend: tuple[Any, str, str],
        note: str,
        symbol_hint: str,
        decision: DecisionResult | None,
    ) -> ChartAnalysisSchema:
        client, model, source = backend
        payload = _user_payload(note=note, symbol_hint=symbol_hint, decision=decision)
        data_url = (
            f"data:{image.mime};base64,{base64.b64encode(image.data).decode('ascii')}"
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": payload},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        content = _vision_completion(client, model, messages, prefer_json=True)
        parsed = _parse_llm_json(content)
        return assemble_chart_analysis(parsed, source=source, decision=decision)


def analyze_locally(
    *,
    note: str = "",
    symbol_hint: str = "",
    decision: DecisionResult | None = None,
) -> ChartAnalysisSchema:
    """Navigate positions from desk engines when vision is unavailable."""
    if decision is not None:
        return assemble_chart_analysis(
            _local_from_decision(decision, note=note),
            source="local",
            decision=decision,
        )
    symbol = _normalize_symbol(symbol_hint)
    observations = [
        "Vision is off (Gemini is geo-blocked in some regions; no Groq/OpenAI key). "
        "The screenshot pixels were not read."
    ]
    if note:
        observations.append(f"Trader note: {note[:200]}")
    if symbol:
        thesis = (
            f"{symbol} is not on the tracked desk. Without vision the analyst "
            "cannot read the screenshot. Use a tracked ticker (BTC, NVDA, …) "
            "or request it from admin."
        )
        structure = "No live evidence — symbol is not tracked."
    else:
        thesis = (
            "No vision key and no ticker. Type a tracked symbol (BTC, ETH, NVDA) "
            "so desk engines can map WAIT / WATCH / EXECUTE from live evidence. "
            "A screenshot is optional in this mode."
        )
        structure = "Waiting on a ticker — sitting out is the valid call."
    return assemble_chart_analysis(
        {
            "symbol": symbol,
            "asset_class": "unknown",
            "trend": "unclear",
            "structure": structure,
            "thesis": thesis,
            "observations": observations,
            "positions": [
                {
                    "bias": "no_trade",
                    "setup_name": "Stand aside",
                    "thesis": thesis,
                    "execution_hint": "WAIT",
                    "confidence": 15,
                    "chart_derived": False,
                    "risk_notes": "Add a tracked symbol to use the decision pipeline.",
                }
            ],
            "image_quality": "unreadable",
        },
        source="local",
    )


def _vision_completion(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    *,
    prefer_json: bool,
) -> str:
    """Chat completion that degrades if the node rejects response_format."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    if prefer_json:
        try:
            response = client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or "{}"
        except Exception:
            logger.info("JSON response_format rejected; retrying without it")
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or "{}"


def _parse_llm_json(content: str) -> dict[str, Any]:
    """Parse model JSON, including fenced blocks from local servers."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        logger.warning("Chart analyzer returned non-JSON; using empty parse")
        return {}


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
    positions.sort(key=lambda item: item.confidence, reverse=True)
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
    derived = raw.get("chart_derived", True)
    if isinstance(derived, str):
        derived = derived.strip().lower() in {"1", "true", "yes"}
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
        chart_derived=bool(derived),
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


def _local_from_decision(decision: DecisionResult, *, note: str) -> dict[str, Any]:
    """Build a chart-analysis payload from engines when vision cannot run."""
    trend_score = _category_score(decision, "Trend")
    trend = _trend_from_score(trend_score)
    state = decision.trade_state.value
    exec_hint = decision.execution.signal.value
    if state == "IGNORE":
        bias = "no_trade"
        hint = "WAIT"
        setup = "Stand aside"
    elif trend == "bearish":
        bias = "short"
        hint = exec_hint
        setup = "Desk short location"
    elif trend == "bullish":
        bias = "long"
        hint = exec_hint
        setup = "Desk long location"
    else:
        bias = "no_trade"
        hint = "WATCH" if state == "WATCH" else "WAIT"
        setup = "No clean location"

    risk = decision.risk
    entry = None
    invalidation = None
    targets: list[str] = []
    risk_notes = decision.execution.description
    if risk is not None:
        entry = f"tape; stop {risk.stop_loss:.2f}"
        invalidation = f"stop {risk.stop_loss:.2f}"
        targets = [f"target {risk.take_profit:.2f} ({risk.risk_reward_ratio:.1f}:1)"]
        risk_notes = risk.description

    observations = [
        "Vision unavailable — screenshot was not read. Thesis is from live desk engines.",
    ]
    if note:
        observations.append(f"Trader note: {note[:200]}")
    for item in decision.evidence.items[:6]:
        if item.description:
            observations.append(f"{item.category}: {item.description}")

    asset_class = "unknown"
    resolved = resolve_asset_class(decision.symbol)
    if resolved is not None:
        asset_class = resolved.value

    thesis = (
        f"{decision.symbol} desk state {state}, grade {decision.opportunity.trade_grade}, "
        f"execution {exec_hint}. {decision.summary} "
        "Pixels were not read (Gemini/Groq/OpenAI vision off)."
    )
    positions: list[dict[str, Any]] = [
        {
            "bias": bias,
            "setup_name": setup,
            "thesis": thesis,
            "entry_zone": entry,
            "invalidation": invalidation,
            "targets": targets,
            "risk_notes": risk_notes,
            "execution_hint": hint,
            "confidence": decision.opportunity.opportunity_score,
            "chart_derived": False,
        }
    ]
    if bias != "no_trade":
        positions.append(
            {
                "bias": "no_trade",
                "setup_name": "Stand aside",
                "thesis": "Sitting out remains valid until a location is confirmed on the tape.",
                "execution_hint": "WAIT",
                "confidence": 20,
                "chart_derived": False,
                "risk_notes": "No trade is a first-class decision.",
            }
        )
    return {
        "symbol": decision.symbol,
        "asset_class": asset_class,
        "timeframe": "1h",
        "chart_type": "desk_engines",
        "trend": trend,
        "structure": decision.summary,
        "thesis": thesis,
        "observations": observations[:8],
        "key_levels": [level for level in (invalidation, *targets) if level],
        "positions": positions,
        "image_quality": "unreadable",
        "conflicts": [],
    }


def _category_score(decision: DecisionResult, category: str) -> float | None:
    for item in decision.evidence.items:
        if item.category == category:
            return item.score
    return None


def _trend_from_score(score: float | None) -> str:
    if score is None:
        return "unclear"
    if score >= 60:
        return "bullish"
    if score <= 40:
        return "bearish"
    return "range"


def _user_payload(
    *,
    note: str,
    symbol_hint: str,
    decision: DecisionResult | None,
) -> str:
    parts = [
        "Automatic setup scan. Do not wait for a user question. Read this "
        "screenshot and rank the best possible locations on the tape: "
        "structure, key levels, best long if any, best short if any, and a "
        "stand-aside. Put the highest-confidence setup first. Include "
        "entry_zone, invalidation, targets, and WAIT / WATCH / EXECUTE."
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
