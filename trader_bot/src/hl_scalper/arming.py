from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArmingStatus:
    ok: bool
    reasons: tuple[str, ...]

    @property
    def summary(self) -> str:
        return "armed" if self.ok else ",".join(self.reasons) or "not_armed"


def check_arming(
    *,
    live_enabled: bool,
    allow_live_orders: bool,
    arm_file: Path,
    killed: bool,
    agent_key_env: str = "HL_AGENT_PRIVATE_KEY",
    master_address_env: str = "HL_MASTER_ADDRESS",
) -> ArmingStatus:
    """Dual-control arming for live. Paper ignores this."""
    reasons: list[str] = []
    if not live_enabled:
        reasons.append("live_enabled_false")
    if not allow_live_orders:
        reasons.append("allow_live_orders_false")
    if killed:
        reasons.append("killed")
    if not arm_file.is_file():
        reasons.append("missing_arm_file")
    agent = os.environ.get(agent_key_env, "").strip()
    master = os.environ.get(master_address_env, "").strip()
    if not agent:
        reasons.append("missing_agent_key_env")
    if not master:
        reasons.append("missing_master_address_env")
    # Never accept master private key env — only address.
    if os.environ.get("HL_MASTER_PRIVATE_KEY"):
        reasons.append("master_private_key_present_refuse")
    return ArmingStatus(ok=not reasons, reasons=tuple(reasons))
