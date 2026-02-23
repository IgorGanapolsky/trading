"""Autonomous provider promotion logic for browser automation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_PROMOTION_POLICY: dict[str, Any] = {
    "default_provider": "local",
    "min_attempted": 3,
    "min_success_rate": 0.9,
    "max_cost_per_success_usd": 0.02,
    "latency_weight_per_second": 0.005,
    "cost_weight": 2.0,
    "switch_margin": 0.02,
}


def load_policy(path: Path | None) -> dict[str, Any]:
    """Load promotion policy from JSON file if provided; else defaults."""
    policy = dict(DEFAULT_PROMOTION_POLICY)
    if path is None or not path.exists():
        return policy
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return policy
    if not isinstance(payload, dict):
        return policy
    for key in DEFAULT_PROMOTION_POLICY:
        if key in payload:
            policy[key] = payload[key]
    return policy


def load_previous_provider(state_path: Path) -> str | None:
    """Return previous preferred provider from state file if it exists."""
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("preferred_provider")
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


def recommend_provider(
    summary: dict[str, dict[str, Any]],
    *,
    policy: dict[str, Any] | None = None,
    previous_provider: str | None = None,
) -> dict[str, Any]:
    """Select best provider using reliability-first scoring with hysteresis."""
    cfg = dict(DEFAULT_PROMOTION_POLICY)
    if isinstance(policy, dict):
        cfg.update(policy)

    default_provider = str(cfg["default_provider"]).lower()
    min_attempted = int(cfg["min_attempted"])
    min_success_rate = float(cfg["min_success_rate"])
    max_cost = float(cfg["max_cost_per_success_usd"])
    latency_weight = float(cfg["latency_weight_per_second"])
    cost_weight = float(cfg["cost_weight"])
    switch_margin = float(cfg["switch_margin"])

    candidates: dict[str, dict[str, Any]] = {}
    for provider, row in summary.items():
        attempted = int(row.get("attempted", 0))
        success_rate = row.get("success_rate")
        avg_latency_ms = float(row.get("avg_latency_ms", 0.0))
        cps = row.get("cost_per_success_usd")

        if cps is None:
            cost_per_success = 0.0
        else:
            cost_per_success = float(cps)

        eligible = True
        ineligible_reasons: list[str] = []
        if attempted < min_attempted:
            eligible = False
            ineligible_reasons.append(f"attempted<{min_attempted}")
        if success_rate is None or float(success_rate) < min_success_rate:
            eligible = False
            ineligible_reasons.append(f"success_rate<{min_success_rate:.3f}")
        if provider != "local" and cost_per_success > max_cost:
            eligible = False
            ineligible_reasons.append(f"cost_per_success>{max_cost:.4f}")

        success_rate_num = 0.0 if success_rate is None else float(success_rate)
        latency_seconds = avg_latency_ms / 1000.0
        utility = (
            success_rate_num - (latency_weight * latency_seconds) - (cost_weight * cost_per_success)
        )

        candidates[provider] = {
            "attempted": attempted,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency_ms,
            "cost_per_success_usd": cost_per_success,
            "eligible": eligible,
            "ineligible_reasons": ineligible_reasons,
            "utility": round(utility, 6),
        }

    eligible_items = {k: v for k, v in candidates.items() if v["eligible"]}
    reason = ""
    if eligible_items:
        best_provider, best_row = max(eligible_items.items(), key=lambda item: item[1]["utility"])
        recommended = best_provider
        reason = f"best eligible utility={best_row['utility']:.6f}"
    else:
        if default_provider in summary:
            recommended = default_provider
            reason = "no eligible provider; fallback to default"
        elif summary:
            recommended = max(summary.items(), key=lambda item: int(item[1].get("attempted", 0)))[0]
            reason = "no eligible/default provider; fallback to highest attempted"
        else:
            recommended = default_provider
            reason = "summary empty; fallback to default"

    if previous_provider and previous_provider in candidates and previous_provider in summary:
        prev_utility = float(candidates[previous_provider]["utility"])
        best_utility = (
            float(candidates[recommended]["utility"]) if recommended in candidates else prev_utility
        )
        if recommended != previous_provider and (best_utility - prev_utility) < switch_margin:
            reason = (
                f"hysteresis kept previous provider (margin={best_utility - prev_utility:.6f} "
                f"< {switch_margin:.6f})"
            )
            recommended = previous_provider

    recommended_row = candidates.get(recommended, {})
    confidence = _confidence_from_metrics(recommended_row)
    return {
        "recommended_provider": recommended,
        "confidence": confidence,
        "reason": reason,
        "policy": cfg,
        "candidates": candidates,
    }


def write_provider_state(
    path: Path,
    *,
    recommendation: dict[str, Any],
    run_id: str,
    generated_at_utc: str,
) -> None:
    """Persist current preferred provider as a compact state file."""
    payload = {
        "preferred_provider": recommendation.get("recommended_provider"),
        "confidence": recommendation.get("confidence"),
        "reason": recommendation.get("reason"),
        "source_run_id": run_id,
        "selected_at_utc": generated_at_utc,
        "policy": recommendation.get("policy", {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_promotion_report(
    path: Path,
    *,
    recommendation: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    """Persist detailed promotion evidence report."""
    report = {
        "generated_at_utc": payload.get("generated_at_utc")
        or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "run_id": payload.get("run_id"),
        "summary": payload.get("summary", {}),
        "recommendation": recommendation,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _confidence_from_metrics(metrics: dict[str, Any]) -> float:
    attempted = int(metrics.get("attempted", 0))
    success_rate = float(metrics.get("success_rate") or 0.0)
    if attempted <= 0:
        return 0.0
    sample_factor = min(1.0, attempted / 10.0)
    confidence = success_rate * sample_factor
    return round(max(0.0, min(1.0, confidence)), 4)
