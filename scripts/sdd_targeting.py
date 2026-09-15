#!/usr/bin/env python3
"""SDD targeting rule (InfoQ: When Spec-Driven Development Pays Off).

Spend full specification governance on hard multi-constraint work.
Skip ceremony for throwaway / one-shot / easy tasks (reasoning ≠ SDD).

EXIT 0. JSON: tier=full|quick|skip.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

HARD_KEYWORDS = {
    "cash",
    "fee-yes",
    "risk",
    "kill",
    "gateway",
    "live_blocked",
    "grade",
    "invariant",
    "stop-loss",
    "trade_gateway",
    "coordination",
    "credential",
}


def target(
    *,
    task: str,
    multi_constraint: bool = False,
    regulated: bool = False,
    one_shot_reliable: bool = False,
    throwaway: bool = False,
) -> dict:
    t = (task or "").lower()
    hard_hit = any(k in t for k in HARD_KEYWORDS)
    if throwaway or one_shot_reliable:
        tier = "skip"
        why = "Throwaway or model-reliable one-shot — SDD ceremony is mostly reasoning tax"
    elif regulated or multi_constraint or hard_hit:
        tier = "full"
        why = (
            "Hard/multi-constraint/high-stakes — SDD pays for attribution + audit trail "
            "(InfoQ targeting rule)"
        )
    else:
        tier = "quick"
        why = "Medium task — Quick Flow / BMAD readiness, not full HLD/LLD ceremony"

    return {
        "ok": True,
        "framework": "sdd_targeting",
        "stolen_format": "InfoQ SDD pays-off targeting rule (not a clone)",
        "task": task,
        "tier": tier,
        "why": why,
        "inputs": {
            "multi_constraint": multi_constraint,
            "regulated": regulated,
            "one_shot_reliable": one_shot_reliable,
            "throwaway": throwaway,
            "hard_keyword_hit": hard_hit,
        },
        "control_points_required": (
            ["author", "review_gate", "guided_gen", "drift_detect", "reconcile"]
            if tier == "full"
            else (["author", "verify"] if tier == "quick" else [])
        ),
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True)
    p.add_argument("--multi-constraint", action="store_true")
    p.add_argument("--regulated", action="store_true")
    p.add_argument("--one-shot-reliable", action="store_true")
    p.add_argument("--throwaway", action="store_true")
    args = p.parse_args(argv)
    out = target(
        task=args.task,
        multi_constraint=args.multi_constraint,
        regulated=args.regulated,
        one_shot_reliable=args.one_shot_reliable,
        throwaway=args.throwaway,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
