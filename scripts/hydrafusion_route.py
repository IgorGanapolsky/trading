#!/usr/bin/env python3
"""HydraFusion-style runtime routing FORMAT (InfoQ / GitHub Copilot research).

Source: https://www.infoq.com/news/2026/09/github-hydrafusion/
GitHub blog: Project HydraFusion — Single / Cascade / Critique + five principles.

We do NOT enable Copilot /experimental or clone their multi-provider router.
Local steal maps patterns onto existing Ralph rails:

  Single   → one rail executes (cheap/fast)
  Cascade  → draft → quality gate → escalate only if gate fails
  Critique → draft → isolated read-only critic → one structured revision

Principles enforced in the plan JSON:
  1. complete_accounting — every leg tracked
  2. bounded_execution — timeouts / max legs
  3. isolated_review — critic has no tool/write authority
  4. fail_safe_apply — reject if validation fails
  5. validated_routing — rails must exist before run

EXIT 0 always (plan). EXIT 2 with --strict if required rails missing.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Estimated relative cost units (not USD) — Cascade/Critique should beat "always Opus".
COST_UNITS = {
    "ralph_tick": 1,
    "sdd_targeting": 1,
    "dup_health": 1,
    "agents_md_health": 1,
    "goal_backward": 3,
    "verify_complete": 4,
    "spec_drift": 2,
    "looped_flow": 3,
    "fanout_memory": 1,
    "superpowers_plan": 5,
    "critic_readonly": 2,
    "revision": 3,
}

RAIL_SCRIPTS = {
    "ralph_tick": "scripts/ralph_gsd_tick.py",
    "sdd_targeting": "scripts/sdd_targeting.py",
    "dup_health": "scripts/dup_health.py",
    "agents_md_health": "scripts/agents_md_health.py",
    "goal_backward": "scripts/goal_backward_verify.py",
    "verify_complete": "scripts/superpowers_verify_complete.py",
    "spec_drift": "scripts/spec_drift_review.py",
    "looped_flow": "scripts/looped_flow_tick.py",
    "fanout_memory": "scripts/agent_fanout_memory.py",
    "superpowers_plan": "scripts/superpowers_plan_write.py",
    "critic_readonly": None,  # plan-only: human/sibling agent, no tools
    "revision": "scripts/ralph_gsd_tick.py",
}


def classify(
    *,
    task: str = "",
    multi_constraint: bool = False,
    regulated: bool = False,
    high_risk: bool = False,
    throwaway: bool = False,
    one_shot: bool = False,
    needs_review: bool = False,
) -> str:
    """Return single | cascade | critique."""
    t = (task or "").lower()
    if throwaway or one_shot:
        return "single"
    if regulated or high_risk or needs_review or multi_constraint:
        return "critique"
    if any(k in t for k in ("risk", "kill switch", "live", "credential", "merge", "security")):
        return "critique"
    if any(k in t for k in ("refactor", "multi-file", "pr ", "ci", "flake", "debug")):
        return "cascade"
    if any(k in t for k in ("typo", "rename", "docs only", "status")):
        return "single"
    return "cascade"  # default: try cheap first, escalate on gate fail


def _leg(name: str, rail: str, *, role: str, tools: bool, timeout_s: int) -> dict:
    return {
        "name": name,
        "rail": rail,
        "role": role,
        "tools_allowed": tools,
        "timeout_s": timeout_s,
        "cost_units": COST_UNITS.get(rail, 1),
        "script": RAIL_SCRIPTS.get(rail),
    }


def build_plan(pattern: str, *, task: str) -> dict:
    if pattern == "single":
        legs = [
            _leg("execute", "ralph_tick", role="executor", tools=True, timeout_s=600),
        ]
        why = "Sufficient for independent low-complexity task — optimise latency"
    elif pattern == "cascade":
        legs = [
            _leg("draft", "ralph_tick", role="drafter", tools=True, timeout_s=600),
            _leg("quality_gate", "verify_complete", role="gate", tools=False, timeout_s=300),
            _leg(
                "escalate_if_needed",
                "goal_backward",
                role="escalation",
                tools=True,
                timeout_s=900,
            ),
        ]
        why = "Cheap draft → gate → escalate only if gate fails (HydraFusion Cascade)"
    else:  # critique
        legs = [
            _leg("draft", "ralph_tick", role="drafter", tools=True, timeout_s=900),
            _leg(
                "critique",
                "critic_readonly",
                role="critic",
                tools=False,
                timeout_s=300,
            ),
            _leg("revise_once", "revision", role="reviser", tools=True, timeout_s=900),
            _leg(
                "fail_safe_validate", "goal_backward", role="validator", tools=False, timeout_s=300
            ),
        ]
        why = (
            "Draft → isolated read-only critic (no tools) → one revision → "
            "fail-safe validate (HydraFusion Critique / rubber-duck)"
        )

    total_cost = sum(leg["cost_units"] for leg in legs)
    # Always-on frontier (Opus-class) would be ~sum of max rails; Cascade/Critique save when gate passes early
    always_frontier = 12
    return {
        "pattern": pattern,
        "why": why,
        "task": task,
        "legs": legs,
        "max_legs": len(legs),
        "estimated_cost_units": total_cost,
        "always_frontier_cost_units": always_frontier,
        "estimated_savings_vs_always_frontier": round(1 - (total_cost / always_frontier), 3)
        if always_frontier
        else None,
        "cascade_early_exit": pattern == "cascade",
        "critique_isolated": pattern == "critique",
    }


def principles_checklist(plan: dict) -> list[dict]:
    legs = plan["legs"]
    critic = [leg for leg in legs if leg["role"] == "critic"]
    validator = [leg for leg in legs if leg["role"] in {"validator", "gate"}]
    return [
        {
            "id": "complete_accounting",
            "ok": all("cost_units" in leg for leg in legs),
            "detail": f"tracked legs={len(legs)} total_units={plan['estimated_cost_units']}",
        },
        {
            "id": "bounded_execution",
            "ok": all(leg.get("timeout_s", 0) > 0 for leg in legs) and plan["max_legs"] <= 6,
            "detail": f"max_legs={plan['max_legs']} timeouts set",
        },
        {
            "id": "isolated_review",
            "ok": all(not c["tools_allowed"] for c in critic) if critic else True,
            "detail": "critic is tool-less" if critic else "n/a (no critic leg)",
        },
        {
            "id": "fail_safe_apply",
            "ok": bool(validator) or plan["pattern"] == "single",
            "detail": "validation/gate leg present before accept" if validator else "single path",
        },
        {
            "id": "validated_routing",
            "ok": True,  # filled by route() after filesystem check
            "detail": "rails pre-checked at route()",
        },
    ]


def validate_rails(plan: dict, *, root: Path = ROOT) -> list[dict]:
    missing = []
    for leg in plan["legs"]:
        script = leg.get("script")
        if script is None:
            continue  # critic_readonly is intentional plan-only
        path = root / script
        if not path.exists():
            missing.append({"rail": leg["rail"], "script": script})
    return missing


def route(
    *,
    task: str = "",
    multi_constraint: bool = False,
    regulated: bool = False,
    high_risk: bool = False,
    throwaway: bool = False,
    one_shot: bool = False,
    needs_review: bool = False,
    root: Path = ROOT,
) -> dict:
    pattern = classify(
        task=task,
        multi_constraint=multi_constraint,
        regulated=regulated,
        high_risk=high_risk,
        throwaway=throwaway,
        one_shot=one_shot,
        needs_review=needs_review,
    )
    plan = build_plan(pattern, task=task or "unspecified")
    missing = validate_rails(plan, root=root)
    principles = principles_checklist(plan)
    for p in principles:
        if p["id"] == "validated_routing":
            p["ok"] = len(missing) == 0
            p["detail"] = "all rails present" if not missing else f"missing={missing}"

    return {
        "ok": len(missing) == 0 and all(p["ok"] for p in principles),
        "framework": "hydrafusion_route",
        "stolen_format": (
            "GitHub HydraFusion / InfoQ — Single|Cascade|Critique + five principles "
            "(not Copilot /experimental)"
        ),
        "source": {
            "infoq": "https://www.infoq.com/news/2026/09/github-hydrafusion/",
            "github_blog": (
                "https://github.blog/ai-and-ml/github-copilot/"
                "project-hydrafusion-frontier-quality-via-multi-model-orchestration/"
            ),
        },
        "signals": {
            "task": task,
            "multi_constraint": multi_constraint,
            "regulated": regulated,
            "high_risk": high_risk,
            "throwaway": throwaway,
            "one_shot": one_shot,
            "needs_review": needs_review,
        },
        "plan": plan,
        "principles": principles,
        "missing_rails": missing,
        "map_to_ours": {
            "single": "ralph_gsd_tick / quick path",
            "cascade": "draft → superpowers_verify_complete → goal_backward escalate",
            "critique": "draft → tool-less critic → one revision → goal_backward",
        },
        "practices": {
            "prefer": "Cascade by default; Critique for risk; Single for throwaways",
            "never": "Always-frontier model for every tick; critic with write/tools",
        },
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", default="")
    p.add_argument("--multi-constraint", action="store_true")
    p.add_argument("--regulated", action="store_true")
    p.add_argument("--high-risk", action="store_true")
    p.add_argument("--throwaway", action="store_true")
    p.add_argument("--one-shot", action="store_true")
    p.add_argument("--needs-review", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = route(
        task=args.task,
        multi_constraint=args.multi_constraint,
        regulated=args.regulated,
        high_risk=args.high_risk,
        throwaway=args.throwaway,
        one_shot=args.one_shot,
        needs_review=args.needs_review,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
