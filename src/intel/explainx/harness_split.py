"""Planner vs executor split stolen from Claude Commerce Agents FORMAT.

Shopping-agent analog = planner (dry-run, research). Merchant-agent analog =
executor (TradeGateway / paper submit / residual exits). Different guardrails
and different evals. Not a checkout clone. Anthropic 35%/60% figures are not ours.
"""

from __future__ import annotations

from typing import Any

PLANNER_MARKERS = (
    "--dry-run",
    "--status",
    "audit_open_inventory",
    "explainx_trending",
    "judge_panel",
    "system_health_check",
)
EXECUTOR_MARKERS = (
    "--manage-exits",
    "residual_ic_manager",
    "spy_put_credit.py",
)
DENIED_MARKERS = (
    "close_position",
    "liquidat",
    "submit_order",
    "reset-weekly",
    "reset-kill-switch",
    "reset-live-block",
    "no-limits",
    "iron_condor_entry",
    "ic_simple_entry",
)


def classify_command(command: str, *, live_blocked: bool = True, paper_only: bool = True) -> dict[str, Any]:
    text = " ".join(str(command or "").split())
    lowered = text.lower()

    denied = [marker for marker in DENIED_MARKERS if marker in lowered]
    if denied:
        return {
            "role": "denied",
            "commerce_analog": None,
            "command": text,
            "allowed": False,
            "reason": "boundary or invented reset",
            "matched": denied,
            "eval": "must_not_run",
            "paper_only": paper_only,
            "live_blocked": live_blocked,
            "vendor_conversion_figures_are_ours": False,
        }

    if any(marker in lowered for marker in PLANNER_MARKERS):
        return {
            "role": "planner",
            "commerce_analog": "shopping_agent",
            "command": text,
            "allowed": True,
            "reason": "plan/status only; a dry-run is not an executed trade",
            "eval": "plan_quality_not_fill",
            "paper_only": paper_only,
            "live_blocked": live_blocked,
            "vendor_conversion_figures_are_ours": False,
        }

    executor_hit = any(marker in lowered for marker in EXECUTOR_MARKERS)
    if executor_hit:
        live_intent = "--live" in lowered or "trading_env=live" in lowered
        allowed = (not live_intent) and paper_only
        return {
            "role": "executor",
            "commerce_analog": "merchant_agent",
            "command": text,
            "allowed": allowed,
            "reason": (
                "live submit refused; this split does not grant live"
                if live_intent or not paper_only
                else "policy-accurate paper path; not a conversion-optimizing shopper"
            ),
            "eval": "policy_accuracy_not_conversion",
            "paper_only": paper_only,
            "live_blocked": True if live_intent or not paper_only else live_blocked,
            "vendor_conversion_figures_are_ours": False,
        }

    return {
        "role": "unknown",
        "commerce_analog": None,
        "command": text,
        "allowed": False,
        "reason": "unclassified; default deny",
        "eval": "must_not_run",
        "paper_only": paper_only,
        "live_blocked": live_blocked,
        "vendor_conversion_figures_are_ours": False,
    }
