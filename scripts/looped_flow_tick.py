#!/usr/bin/env python3
"""Looped-flow ticks for agent harness (FORMAT steal — not ML training).

Paper: Thinking with Looped Flows (arXiv:2609.11801), via @omarsar0.
Insight: looped compute helps only if early updates set up later ones — train with
*local* objectives (denoising), not only the final loss. At inference, a finer
time grid spends more compute.

Our analog (no neural nets, no ARC trainer):
  noise = fraction of goal-backward conditions still FALSE
  each loop step: pick the noisiest failing condition as the local objective
  shared residual_id ties steps (shared noise)
  more --loop-steps = finer grid / more verify compute

EXIT 0 always (report). EXIT 2 with --strict if final noise > 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from goal_backward_verify import (  # noqa: E402
    cash_conditions,
    harness_conditions,
    verify_goal,
)


def _noise(results: list[dict]) -> float:
    if not results:
        return 1.0
    fails = sum(1 for r in results if not r.get("ok"))
    return fails / len(results)


def _local_objective(results: list[dict]) -> dict | None:
    """Pick one failing condition — local denoising target for this step."""
    for r in results:
        if not r.get("ok"):
            return {
                "id": r.get("id"),
                "must_be_true": r.get("must_be_true"),
                "why": "Local objective: early ticks must set up later ones (looped flows)",
            }
    return None


def run_loop(
    *,
    goal: str = "harness",
    steps: int = 3,
    shared_seed: str | None = None,
    verify_fn=None,
) -> dict:
    """Run a looped-flow of local goal-backward denoising steps."""
    steps = max(1, min(steps, 16))  # bound compute
    seed = shared_seed or f"{goal}:{datetime.now(UTC).strftime('%Y%m%d')}"
    residual_id = hashlib.sha1(seed.encode(), usedforsecurity=False).hexdigest()[:12]

    conditions = harness_conditions() if goal == "harness" else cash_conditions()
    goal_label = (
        "Harness residual is evidence-true (goal-backward)"
        if goal == "harness"
        else "Cash residual operationally true (not fee-yes)"
    )
    verify = verify_fn or (lambda: verify_goal(goal_label, conditions))

    trajectory: list[dict] = []
    noise_levels: list[float] = []
    last: dict = {}

    for t in range(steps):
        last = verify()
        noise = _noise(last.get("conditions") or [])
        noise_levels.append(round(noise, 4))
        local = _local_objective(last.get("conditions") or [])
        trajectory.append(
            {
                "step": t,
                "noise": round(noise, 4),
                "passed": last.get("passed"),
                "total": last.get("total"),
                "local_objective": local,
                "ok": last.get("ok"),
            }
        )
        # Early stop when fully denoised
        if last.get("ok"):
            break

    # Temporal association: noise should be non-increasing when live proofs improve
    monotone = all(
        noise_levels[i] >= noise_levels[i + 1] - 1e-9 for i in range(len(noise_levels) - 1)
    )

    return {
        "ok": bool(last.get("ok")),
        "framework": "looped_flow_tick",
        "stolen_format": (
            "Thinking with Looped Flows (arXiv:2609.11801) — local denoising + "
            "finer time grid FORMAT; not a model trainer / ARC clone"
        ),
        "source": {
            "paper": "https://arxiv.org/abs/2609.11801",
            "tweet": "https://x.com/omarsar0/status/2098807354343260366",
        },
        "goal": goal,
        "steps_requested": steps,
        "steps_run": len(trajectory),
        "shared_noise_seed": seed,
        "residual_id": residual_id,
        "noise_levels": noise_levels,
        "final_noise": noise_levels[-1] if noise_levels else 1.0,
        "noise_nonincreasing": monotone,
        "trajectory": trajectory,
        "final_local_objective": trajectory[-1]["local_objective"] if trajectory else None,
        "practices": {
            "message": "Spend more compute via finer loop grid; each step has a local TRUE target",
            "prefer": "Early ticks clear setup conditions so later ticks can converge",
            "never": "Train looped neural nets / claim ARC scores / skip local verify",
        },
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--goal", choices=["harness", "cash"], default="harness")
    p.add_argument(
        "--loop-steps",
        type=int,
        default=3,
        help="Finer grid = more compute (paper: accuracy↑ with more steps)",
    )
    p.add_argument("--seed", default=None, help="Shared noise seed across steps")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = run_loop(goal=args.goal, steps=args.loop_steps, shared_seed=args.seed)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
