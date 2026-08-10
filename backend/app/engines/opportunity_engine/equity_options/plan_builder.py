"""Build staged smart-execution plans for Layer 3 ideas."""

from __future__ import annotations

from app.engines.opportunity_engine.equity_options.types import (
    DirectionBias,
    EquitySetupType,
    ExecutionPlan,
    MomentumSnapshot,
    OptionCandidate,
    ProfitZone,
    StagedEntry,
)


def _harvest_zones(selected: OptionCandidate | None) -> tuple[list[ProfitZone], float]:
    """Scale harvest targets with DTE — short-dated books take sooner."""
    dte = selected.dte if selected is not None and selected.dte > 0 else 25
    if dte <= 14:
        # Theta burns fast: take earlier, leave a thinner runner
        zones = [
            ProfitZone(40.0, 25.0, "Scale 25% at +40% premium (short DTE)"),
            ProfitZone(80.0, 30.0, "Scale 30% at +80% premium"),
            ProfitZone(150.0, 25.0, "Scale 25% at +150% premium"),
        ]
        runner = 20.0
    elif dte <= 35:
        zones = [
            ProfitZone(50.0, 20.0, "Scale 20% at +50% premium"),
            ProfitZone(100.0, 25.0, "Scale 25% at +100% premium"),
            ProfitZone(200.0, 25.0, "Scale 25% at +200% premium"),
        ]
        runner = 30.0
    else:
        # More time: let convexity work; harvest a bit later
        zones = [
            ProfitZone(60.0, 15.0, "Scale 15% at +60% premium (longer DTE)"),
            ProfitZone(120.0, 25.0, "Scale 25% at +120% premium"),
            ProfitZone(250.0, 25.0, "Scale 25% at +250% premium"),
        ]
        runner = 35.0
    return zones, runner


def build_execution_plan(
    symbol: str,
    direction: DirectionBias,
    momentum: MomentumSnapshot,
    selected: OptionCandidate | None,
    *,
    setup_type: EquitySetupType = "momentum_continuation",
    max_risk_usd: float = 1000.0,
) -> ExecutionPlan:
    """Create Entry 1/2/3 plan with hard/soft invalidation and premium harvest."""
    price = momentum.price
    breakout = momentum.breakout_level or round(price * 1.03, 2)
    support = momentum.support_level or round(price * 0.94, 2)
    atr_pad = max(price * (momentum.atr_pct / 100.0) * 0.35, price * 0.008)
    is_breakout = setup_type == "breakout_convexity"
    dma20_hint = f"20DMA ({momentum.dist_20dma_pct:+.1f}% now)"

    if direction == "long":
        if is_breakout:
            e1 = round(max(price, breakout - atr_pad * 0.15), 2)
            e2 = round(breakout + atr_pad * 0.15, 2)
            e3 = round(breakout + atr_pad * 0.85, 2)
            setup_name = "Bullish breakout convexity"
            e1_cond = f"Probe: {symbol} holds the breakout shelf near ${e1:.2f}"
            e2_cond = f"Confirm: acceptance above ${e2:.2f} (breakout level ${breakout:.2f})"
            e3_cond = (
                f"Expand: continuation above ${e3:.2f} with rel vol ≥1.5× "
                f"(now {momentum.relative_volume:.1f}×)"
            )
        else:
            e1 = round(max(price * 0.995, support + atr_pad), 2)
            e2 = round(price + atr_pad * 0.35, 2)
            e3 = round(price + atr_pad, 2)
            setup_name = "Bullish momentum continuation"
            e1_cond = f"Probe: dip-hold above ${e1:.2f} with bid stable"
            e2_cond = f"Confirm: reclaim / push through ${e2:.2f} along {dma20_hint}"
            e3_cond = (
                f"Expand: trend add above ${e3:.2f} if structure intact "
                f"(rel vol {momentum.relative_volume:.1f}×)"
            )

        invalidate_px = round(support - atr_pad * 0.5, 2)
        entries = [
            StagedEntry(1, "Probe", 25.0, e1_cond, e1),
            StagedEntry(2, "Confirm", 35.0, e2_cond, e2),
            StagedEntry(3, "Expand", 40.0, e3_cond, e3),
        ]
        invalidation = [
            f"HARD: daily close below structure ${invalidate_px:.2f} "
            f"(support {support:.2f} − pad)",
            f"HARD: call bid collapses >60% while underlying still holds "
            f"(timing / IV crush — stand down new adds)",
            f"SOFT: loses {dma20_hint} and fails to reclaim within 2 sessions "
            f"— pause Expand (E3), keep risk cold",
            "SOFT: relative volume fades <0.8× on failed continuation day "
            "— do not chase Expand",
        ]
        runner_rule = (
            f"Leave ~{{runner}}% after harvest targets. Trail runner vs "
            f"${invalidate_px:.2f} daily close; cut runner if HARD invalidation hits. "
            "Do not roll into a farther lottery strike just to 'be in'."
        )
    else:
        if is_breakout:
            e1 = round(min(price, support + atr_pad * 0.15), 2)
            e2 = round(support - atr_pad * 0.15, 2)
            e3 = round(support - atr_pad * 0.85, 2)
            setup_name = "Bearish breakdown convexity"
            e1_cond = f"Probe: {symbol} rejects the breakdown shelf near ${e1:.2f}"
            e2_cond = f"Confirm: acceptance below ${e2:.2f} (breakdown ${support:.2f})"
            e3_cond = f"Expand: continuation below ${e3:.2f} with volume expansion"
        else:
            e1 = round(min(price * 1.005, breakout - atr_pad), 2)
            e2 = round(price - atr_pad * 0.35, 2)
            e3 = round(price - atr_pad, 2)
            setup_name = "Bearish momentum continuation"
            e1_cond = f"Probe: bounce-fail below ${e1:.2f}"
            e2_cond = f"Confirm: push through ${e2:.2f} under {dma20_hint}"
            e3_cond = f"Expand: trend add below ${e3:.2f} if structure intact"

        invalidate_px = round(breakout + atr_pad * 0.5, 2)
        entries = [
            StagedEntry(1, "Probe", 25.0, e1_cond, e1),
            StagedEntry(2, "Confirm", 35.0, e2_cond, e2),
            StagedEntry(3, "Expand", 40.0, e3_cond, e3),
        ]
        invalidation = [
            f"HARD: daily close back above ${invalidate_px:.2f} "
            f"(breakdown fail)",
            "HARD: put premium collapses >60% without structure confirmation "
            "— stop new adds",
            f"SOFT: reclaim of {dma20_hint} with strength — pause Expand (E3)",
            "SOFT: short-covering volume spike without lower highs — wait, don't average",
        ]
        runner_rule = (
            f"Leave ~{{runner}}% after harvest. Cover runner on daily close above "
            f"${invalidate_px:.2f} or on HARD invalidation. "
            "Harvest put mark-to-market — ignore underlying strike theater."
        )

    profit_zones, runner_pct = _harvest_zones(selected)
    runner_rule = runner_rule.format(runner=f"{runner_pct:.0f}")

    notes_parts = [
        "Scores are watch guidance, not an order. Risk Engine still owns live size later.",
        "Harvest option mid/mark expansion — do not wait for strike breakeven.",
    ]
    if selected is not None:
        mid = f"${selected.mid:.2f}" if selected.mid is not None else "n/a"
        notes_parts.append(
            f"Preferred: {selected.expiry} ${selected.strike:.0f} {selected.right} "
            f"(DTE {selected.dte}, mid {mid}, score {selected.overall_score:.0f})."
        )
        if selected.dte <= 14:
            notes_parts.append("Short DTE: respect early harvest; theta is the clock.")
    else:
        notes_parts.append(
            "No liquid chain row yet — plan uses underlying structure only "
            "(data_quality may be degraded)."
        )

    return ExecutionPlan(
        setup_name=setup_name,
        direction=direction,
        max_risk_usd=max_risk_usd,
        entries=entries,
        invalidation=invalidation,
        profit_zones=profit_zones,
        runner_pct=runner_pct,
        runner_rule=runner_rule,
        notes=" ".join(notes_parts),
    )
