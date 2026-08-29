"""Frozen paper-bot policy — knobs + features so training can replay executions.

``policy_id`` hashes knobs only (the live rule set). Per-trade market features
live beside it so the same policy can be duplicated against new prints.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

POLICY_SCHEMA = "paper_policy.v1"
PREFERRED_L2_SETUPS = frozenset({"funding_extreme", "liq_flush"})
SQUEEZE_EXPANSION_SETUP = "squeeze_expansion"
SKIP_MOMENTUM_VS_CROWDED_FUNDING = True
SKIP_CME_VS_CROWDED_COT = True
# Honest labels: ±0.05% is noise, not a win.
MIN_WIN_RETURN_PCT = 0.5
MIN_LOSS_RETURN_PCT = -0.5
# 2026-08-29 CSV: equity stock paper 3W/9L; crypto L2 (basis_rich/liq_flush) 0/2.
# Proof sleeve is crypto_perp_v2. Empty this set to resume those factories.
PAUSED_NEW_OPEN_SOURCES = frozenset({"equity_setup", "crypto_setup"})


def candidate_rank_tier(setup_type: str) -> int:
    """Higher tier is tried first. Expansion trigger > L2 crowding > momentum."""
    if setup_type == SQUEEZE_EXPANSION_SETUP:
        return 2
    return 1 if setup_type in PREFERRED_L2_SETUPS else 0


def sort_paper_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer L2 setups, then confidence/opportunity score."""
    return sorted(
        candidates,
        key=lambda c: (
            candidate_rank_tier(str(c.get("setup_type") or "")),
            float(c.get("score") or 0.0),
        ),
        reverse=True,
    )


def momentum_fights_crowded_funding(
    direction: str,
    funding_bps: float | None,
    extreme_bps: float,
) -> bool:
    """True when perp momentum is chasing the crowded funding side."""
    if not SKIP_MOMENTUM_VS_CROWDED_FUNDING:
        return False
    if funding_bps is None:
        return False
    if extreme_bps <= 0:
        return False
    if direction == "long" and funding_bps >= extreme_bps:
        return True
    return direction == "short" and funding_bps <= -extreme_bps


def policy_id_for_knobs(knobs: dict[str, Any]) -> str:
    canonical = json.dumps(knobs, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def parse_policy_blob(notes: str | None) -> dict[str, Any] | None:
    """Extract the JSON policy snapshot from a paper_open note string."""
    if not notes:
        return None
    marker = " | policy="
    idx = notes.find(marker)
    if idx < 0:
        return None
    rest = notes[idx + len(marker) :]
    close_at = rest.find(" | close=")
    if close_at >= 0:
        rest = rest[:close_at]
    try:
        payload = json.loads(rest)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def format_policy_note_suffix(policy: dict[str, Any] | None) -> str:
    if not policy:
        return ""
    blob = json.dumps(policy, sort_keys=True, default=str, separators=(",", ":"))
    return f"policy={blob}"


def snapshot_live_knobs(
    *,
    size_usd: float,
    starting_cash: float,
) -> dict[str, Any]:
    """Capture the bot parameters that were live at this moment."""
    from dataclasses import asdict

    from app.engines.opportunity_engine import scanner as l2
    from app.engines.paper_agent import agent as paper_agent
    from app.engines.paper_agent import broker, confirm
    from app.engines.paper_agent import crypto_perp_v2 as v2
    from app.engines.runner_engine.crypto_learn import (
        MIN_CLOSED_TO_APPLY,
        get_crypto_learn_coefficients,
    )

    coeffs = get_crypto_learn_coefficients()
    return {
        "min_confidence": paper_agent.MIN_CONFIDENCE,
        "max_new_opens_per_day": paper_agent.MAX_NEW_OPENS_PER_DAY,
        "max_crypto_perp_v2_opens_per_day": paper_agent.MAX_CRYPTO_PERP_V2_OPENS_PER_DAY,
        "max_cme_futures_opens_per_day": paper_agent.MAX_CME_FUTURES_OPENS_PER_DAY,
        "max_squeeze_expansion_opens_per_day": paper_agent.MAX_SQUEEZE_EXPANSION_OPENS_PER_DAY,
        "discover_interval_seconds": paper_agent._DISCOVER_INTERVAL_SECONDS,
        "starting_cash": starting_cash,
        "size_usd": size_usd,
        "slippage_bps": broker.SLIPPAGE_BPS,
        "exit_fallback_take_profit_pct": broker.TAKE_PROFIT_PCT,
        "exit_fallback_stop_loss_pct": broker.STOP_LOSS_PCT,
        "max_hold_hours": broker.MAX_HOLD_HOURS,
        "confirm_min_grade": confirm.MIN_GRADE,
        "risk_veto_threshold": confirm.RISK_VETO_THRESHOLD,
        "risk_veto_min_rr": confirm.RISK_VETO_MIN_RR,
        "fng_block_long_above": confirm.FNG_BLOCK_LONG_ABOVE,
        "fng_block_short_below": confirm.FNG_BLOCK_SHORT_BELOW,
        "earnings_veto_days": confirm.EARNINGS_VETO_DAYS,
        "learn_min_closed_to_apply": MIN_CLOSED_TO_APPLY,
        "learn": asdict(coeffs),
        "l2_funding_extreme_bps": l2._FUNDING_EXTREME_BPS,
        "l2_funding_soft_bps": l2._FUNDING_SOFT_BPS,
        "l2_liq_min_total_usd": l2._LIQ_MIN_TOTAL_USD,
        "l2_watch_min_confidence": l2._WATCH_MIN_CONFIDENCE,
        "v2_min_confidence": v2.MIN_CONFIDENCE,
        "v2_momentum_bars": v2._MOMENTUM_BARS,
        "v2_universe_n": len(v2.V2_UNIVERSE),
        "preferred_l2_setups": sorted(PREFERRED_L2_SETUPS),
        "skip_momentum_vs_crowded_funding": SKIP_MOMENTUM_VS_CROWDED_FUNDING,
        "skip_cme_vs_crowded_cot": SKIP_CME_VS_CROWDED_COT,
        "paused_new_open_sources": sorted(PAUSED_NEW_OPEN_SOURCES),
        "min_win_return_pct": MIN_WIN_RETURN_PCT,
        "min_loss_return_pct": MIN_LOSS_RETURN_PCT,
    }


def snapshot_paper_execution(
    *,
    size_usd: float,
    starting_cash: float,
    take_profit_pct: float,
    stop_loss_pct: float,
    source: str,
    setup_type: str,
    direction: str,
    confidence: float,
    opportunity_score: float,
    factors: list[str] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Knobs (hashed) + this trade's features for later duplication."""
    knobs = snapshot_live_knobs(size_usd=size_usd, starting_cash=starting_cash)
    features: dict[str, Any] = {
        "source": source,
        "setup_type": setup_type,
        "direction": direction,
        "confidence": confidence,
        "opportunity_score": opportunity_score,
        "take_profit_pct": take_profit_pct,
        "stop_loss_pct": stop_loss_pct,
        "rank_tier": candidate_rank_tier(setup_type),
        "factors": list(factors or [])[:8],
    }
    if extras:
        for key, value in extras.items():
            if key in {"policy", "knobs"} or value is None or value == "":
                continue
            if isinstance(value, (dict, list)):
                continue
            features[key] = value
    policy_id = policy_id_for_knobs(knobs)
    return {
        "schema": POLICY_SCHEMA,
        "policy_id": policy_id,
        "knobs": knobs,
        "features": features,
    }


def attach_close_to_policy(
    policy: dict[str, Any] | None,
    *,
    close_reason: str | None,
    honest_return_pct: float | None,
    optimistic_return_pct: float | None,
    outcome: str | None,
) -> dict[str, Any]:
    """Keep the open snapshot; append close labels for replay."""
    body = dict(policy or {})
    body["close"] = {
        "reason": close_reason,
        "honest_return_pct": honest_return_pct,
        "optimistic_return_pct": optimistic_return_pct,
        "outcome": outcome,
    }
    return body
