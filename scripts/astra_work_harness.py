#!/usr/bin/env python3
"""CLI: OpenAI GPT-6 Astra Next-Generation Work & Agent Harness for Trading Ops.

Source: https://openai.com/index/gpt-6-astra-next-generation-work/

Commands:
  --doctor             Run Astra work agent harness compliance diagnostics
  --plan <goal>        Decompose goal into Supervisor DAG with risk tiering
  --run-loop <goal>    Execute Astra Manager Loop with mid-turn steering
  --classify <tool>    Classify risk level of a tool or action
  --json               Format output as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.astra_work_harness import (  # noqa: E402
    AstraManagerLoop,
    classify_action_risk,
    decompose_goal_to_dag,
    diagnose_astra_harness,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GPT-6 Astra Next-Generation Work & Agent Harness for Trading Ops"
    )
    parser.add_argument("--doctor", action="store_true", help="Run harness doctor diagnostics")
    parser.add_argument("--plan", type=str, default="", help="Decompose goal into Supervisor DAG")
    parser.add_argument(
        "--run-loop",
        type=str,
        default="",
        help="Execute Manager Loop over goal DAG with mid-turn steering",
    )
    parser.add_argument("--classify", type=str, default="", help="Classify tool action risk level")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    if args.doctor:
        report = diagnose_astra_harness(ROOT)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            status_str = "PASS" if report.ok else "FAIL"
            print(
                f"=== GPT-6 Astra Work Harness Doctor: {status_str} ({report.score}/{report.max_score}) ==="
            )
            for check, passed in report.checks.items():
                print(f"  [{'✓' if passed else '✗'}] {check}: {report.details.get(check, '')}")
            if report.failing:
                print(f"Failing checks: {', '.join(report.failing)}")
            print(f"Content hash: {report.content_hash}")
        return 0 if report.ok else 1

    if args.classify:
        risk = classify_action_risk(args.classify)
        if args.json:
            print(json.dumps({"tool": args.classify, "risk_level": risk.value}, indent=2))
        else:
            print(f"Tool: {args.classify} -> Risk Level: {risk.value.upper()}")
        return 0

    if args.plan:
        plan = decompose_goal_to_dag(args.plan)
        if args.json:
            print(json.dumps(plan.to_dict(), indent=2))
        else:
            print(f"=== Astra Supervisor DAG Plan for: '{plan.goal}' ===")
            print(f"Status: {'OK' if plan.ok else 'FAIL'}")
            print("Execution Order:")
            for i, sid in enumerate(plan.execution_order, 1):
                step = next(s for s in plan.steps if s.step_id == sid)
                print(f"  {i}. [{step.risk_level.value.upper()}] {step.step_id} ({step.role})")
                print(f"     Description: {step.description}")
                print(f"     Tools: {', '.join(step.tools)}")
                print(f"     Acceptance Criteria: {', '.join(step.acceptance_criteria)}")
        return 0 if plan.ok else 1

    if args.run_loop:
        plan = decompose_goal_to_dag(args.run_loop)
        if not plan.ok:
            print(f"Error decomposing goal: {plan.failing}", file=sys.stderr)
            return 1
        manager = AstraManagerLoop(plan)
        receipt = manager.execute_loop()
        if args.json:
            print(json.dumps(receipt.to_dict(), indent=2))
        else:
            print(f"=== Astra Manager Loop Execution: {receipt.receipt_id} ===")
            print(f"Goal: {receipt.goal}")
            print(f"Overall Status: {'SUCCESS' if receipt.ok else 'FAILED'}")
            print(
                f"Steps: {receipt.steps_completed}/{receipt.steps_total} completed, "
                f"{receipt.steps_steered} steered, {receipt.steps_failed} failed"
            )
            print(f"Duration: {receipt.total_duration_ms} ms")
            for res in receipt.results:
                print(f"  - [{res['status'].upper()}] {res['step_id']}: {res['output_summary']}")
                if res.get("steering_applied"):
                    print(f"    Steering: {res['steering_applied']}")
        return 0 if receipt.ok else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
