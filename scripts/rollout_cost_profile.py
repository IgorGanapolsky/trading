#!/usr/bin/env python3
"""Profile agent rollouts. Do not replace GRPO. Do not clone FlashREINFORCE or Molt.

Episode FORMAT (https://music.youtube.com/watch?v=v-LD_XChPkA):
  1. Measure per-trajectory duration, stragglers, queue, tokens, tool calls,
     success, and cost per *solved* task before changing the trainer.
  2. Fewer rollouts are not automatically fewer GPU-hours or dollars.
  3. Tool-use retention is a gate (GRPO going to 0 tool calls is a fail).
  4. Contained family with a verifier: spy_put_credit dry-run (paper).

GRPO in this repo remains optional research, not the operator path.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_FAMILY = "spy_put_credit_dry_run"
GRPO_STATUS = "optional_research_not_production"
SOURCE = "https://music.youtube.com/watch?v=v-LD_XChPkA"
COST_CUT_FLOOR = 0.15  # 15% cheaper per solved task
STRAGGLER_MULT = 2.0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ordered = sorted(xs)
    k = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
    return float(ordered[k])


def profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    durs = [float(r["duration_s"]) for r in rows if r.get("duration_s") is not None]
    queues = [float(r["queue_s"]) for r in rows if r.get("queue_s") is not None]
    tokens = [float(r["tokens"]) for r in rows if r.get("tokens") is not None]
    tools = [float(r.get("tool_calls") or 0) for r in rows]
    idles = [float(r["idle_s"]) for r in rows if r.get("idle_s") is not None]
    gpu = [float(r["gpu_hours"]) for r in rows if r.get("gpu_hours") is not None]
    costs = [float(r["cost_usd"]) for r in rows if r.get("cost_usd") is not None]
    solved = [r for r in rows if r.get("success") is True and r.get("verified") is True]
    median = statistics.median(durs) if durs else None
    stragglers = 0
    if median is not None and median > 0:
        stragglers = sum(1 for d in durs if d > STRAGGLER_MULT * median)
    cost_total = sum(costs) if costs else None
    n_solved = len(solved)
    cost_per_solved = None
    if cost_total is not None and n_solved > 0 and len(costs) == n:
        cost_per_solved = cost_total / n_solved
    gpu_per_solved = None
    if gpu and n_solved > 0 and len(gpu) == n:
        gpu_per_solved = sum(gpu) / n_solved
    return {
        "ok": True,
        "framework": "rollout_cost_profile",
        "stolen_format": (
            "FlashREINFORCE episode: profile first; async to cut sync-idle; "
            "tool-use retention gates promotion; half rollouts ≠ half GPU-hours"
        ),
        "source": {"youtube_music": SOURCE},
        "task_family": TASK_FAMILY,
        "grpo_status": GRPO_STATUS,
        "n": n,
        "n_solved": n_solved,
        "success_rate": (n_solved / n) if n else None,
        "p50_duration_s": _pct(durs, 50),
        "p95_duration_s": _pct(durs, 95),
        "straggler_pct": (stragglers / len(durs)) if durs else None,
        "mean_queue_s": (sum(queues) / len(queues)) if queues else None,
        "mean_tokens": (sum(tokens) / len(tokens)) if tokens else None,
        "mean_tool_calls": (sum(tools) / len(tools)) if tools else None,
        "tool_use_zero_rate": (sum(1 for t in tools if t <= 0) / len(tools) if tools else None),
        "sync_idle_s_total": sum(idles) if idles else 0.0,
        "cost_usd_total": cost_total,
        "cost_per_solved_task": cost_per_solved,
        "gpu_hours_per_solved": gpu_per_solved,
        "gpu_hours_measured": len(gpu) == n and n > 0,
        "refuses": [
            "half_rollouts_is_not_half_gpu_hours",
            "do_not_replace_grpo_with_flashreinforce",
            "do_not_clone_nvidia_molt",
            "do_not_infer_gpu_hours_from_rollout_count",
        ],
    }


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Promotion: ≥15% lower cost/solved OR higher success at equal/better cost,
    and tool-use must not collapse to zero if baseline used tools.
    """
    b_tools = baseline.get("mean_tool_calls") or 0.0
    c_tools = candidate.get("mean_tool_calls") or 0.0
    tool_ok = not (b_tools > 0 and c_tools == 0)
    b_cost = baseline.get("cost_per_solved_task")
    c_cost = candidate.get("cost_per_solved_task")
    b_succ = baseline.get("success_rate")
    c_succ = candidate.get("success_rate")
    cost_cut = None
    if isinstance(b_cost, (int, float)) and isinstance(c_cost, (int, float)) and b_cost > 0:
        cost_cut = (b_cost - c_cost) / b_cost
    cost_ok = cost_cut is not None and cost_cut >= COST_CUT_FLOOR
    success_up = (
        isinstance(b_succ, (int, float)) and isinstance(c_succ, (int, float)) and c_succ > b_succ
    )
    cost_not_worse = (
        b_cost is None
        or c_cost is None
        or (
            isinstance(b_cost, (int, float))
            and isinstance(c_cost, (int, float))
            and c_cost <= b_cost
        )
    )
    promote = tool_ok and (cost_ok or (success_up and cost_not_worse))
    reasons: list[str] = []
    if not tool_ok:
        reasons.append("tool_use_collapsed")
    if not promote and tool_ok:
        reasons.append("no_cost_or_success_gain")
    if promote:
        reasons.append("meets_15pct_cost_cut_or_higher_success_at_equal_cost")
    return {
        "promote": promote,
        "tool_use_retention_ok": tool_ok,
        "cost_cut_frac": cost_cut,
        "cost_cut_floor": COST_CUT_FLOOR,
        "success_up": success_up,
        "reasons": reasons,
        "baseline": {
            "n": baseline.get("n"),
            "success_rate": b_succ,
            "cost_per_solved_task": b_cost,
            "mean_tool_calls": b_tools,
            "gpu_hours_per_solved": baseline.get("gpu_hours_per_solved"),
        },
        "candidate": {
            "n": candidate.get("n"),
            "success_rate": c_succ,
            "cost_per_solved_task": c_cost,
            "mean_tool_calls": c_tools,
            "gpu_hours_per_solved": candidate.get("gpu_hours_per_solved"),
        },
        "refuses": [
            "half_rollouts_is_not_half_gpu_hours",
            "do_not_promote_on_raw_reward_alone",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("profile", help="summarize a trajectory JSONL")
    pr.add_argument("--jsonl", required=True, type=Path)
    cmp_ = sub.add_parser("compare", help="baseline vs candidate promotion gate")
    cmp_.add_argument("--baseline", required=True, type=Path)
    cmp_.add_argument("--candidate", required=True, type=Path)
    cmp_.add_argument("--strict", action="store_true", help="exit 2 if not promote")
    args = p.parse_args(argv)
    if args.cmd == "profile":
        report = profile(load_jsonl(args.jsonl))
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    base = profile(load_jsonl(args.baseline))
    cand = profile(load_jsonl(args.candidate))
    report = compare(base, cand)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if args.strict and not report["promote"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
