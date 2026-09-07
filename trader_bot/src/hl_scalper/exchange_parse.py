from __future__ import annotations

from typing import Any


def parse_ioc_fill(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Extract fill sz / avg px from an HL SDK order response.

    Returns keys: ok, status, filled_sz, avg_px, reason.
    """
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "status": "error",
            "filled_sz": 0.0,
            "avg_px": None,
            "reason": "non_dict_response",
        }

    status = str(raw.get("status") or "")
    if status and status.lower() not in {"ok", "success"}:
        return {
            "ok": False,
            "status": "error",
            "filled_sz": 0.0,
            "avg_px": None,
            "reason": f"status:{status}",
        }

    response = raw.get("response")
    if not isinstance(response, dict):
        # Some SDK paths return statuses at top level.
        response = raw

    data = response.get("data") if isinstance(response, dict) else None
    statuses = None
    if isinstance(data, dict):
        statuses = data.get("statuses")
    if statuses is None and isinstance(response, dict):
        statuses = response.get("statuses")
    if not isinstance(statuses, list) or not statuses:
        return {
            "ok": False,
            "status": "unknown",
            "filled_sz": 0.0,
            "avg_px": None,
            "reason": "no_statuses",
        }

    filled_sz = 0.0
    px_notional = 0.0
    reasons: list[str] = []
    for item in statuses:
        if not isinstance(item, dict):
            continue
        if "filled" in item and isinstance(item["filled"], dict):
            f = item["filled"]
            try:
                sz = float(f.get("totalSz") or f.get("sz") or 0)
            except (TypeError, ValueError):
                sz = 0.0
            try:
                px = float(f.get("avgPx") or f.get("px") or 0)
            except (TypeError, ValueError):
                px = 0.0
            if sz > 0 and px > 0:
                filled_sz += sz
                px_notional += sz * px
            reasons.append("filled")
        elif "resting" in item:
            reasons.append("resting")
        elif "error" in item:
            reasons.append(f"error:{item.get('error')}")
        else:
            reasons.append("other")

    if filled_sz <= 0:
        return {
            "ok": False,
            "status": "unfilled",
            "filled_sz": 0.0,
            "avg_px": None,
            "reason": ",".join(reasons) or "unfilled",
        }

    avg_px = px_notional / filled_sz if filled_sz else None
    return {
        "ok": True,
        "status": "filled",
        "filled_sz": filled_sz,
        "avg_px": avg_px,
        "reason": ",".join(reasons) or "filled",
    }
