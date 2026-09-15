#!/usr/bin/env python3
"""Execute a HydraFusion plan (Cascade early-exit + Critique isolation).

Builds on hydrafusion_route.py. InfoQ/GitHub FORMAT — not Copilot /experimental.

Runtime enforcement of the five principles:
  1. complete_accounting — ledger of cost_units per leg actually run
  2. bounded_execution — per-leg timeout
  3. isolated_review — critic cannot call tool scripts
  4. fail_safe_apply — reject when validator/gate fails
  5. validated_routing — refuse to start if rails missing

Cascade: run draft → gate; if gate ok, skip escalation (early exit / savings).
Critique: draft → tool-less critic checklist → one revision → validator.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from hydrafusion_route import route as build_route  # noqa: E402


def _run_rail(script: str | None, *args: str, timeout_s: int = 120) -> dict:
    if script is None:
        return {"ok": False, "error": "no_script"}
    path = ROOT / script
    if not path.exists():
        return {"ok": False, "error": f"missing:{script}"}
    py = ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.exists() else sys.executable
    try:
        r = subprocess.run(  # nosec B603
            [exe, str(path), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "timeout_s": timeout_s}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    out: dict = {"ok": r.returncode == 0, "returncode": r.returncode}
    text = (r.stdout or "").strip()
    if text.startswith("{"):
        try:
            out["json"] = json.loads(text)
        except json.JSONDecodeError:
            out["stdout_head"] = text[:400]
    else:
        out["stdout_head"] = text[:400]
    if r.returncode != 0 and r.stderr:
        out["stderr_head"] = r.stderr[:400]
    return out


def _critic_readonly(draft: dict, *, task: str) -> dict:
    """Rubber-duck critic: no tools — only inspect draft JSON fields."""
    findings = []
    ok = True
    # Isolated: never call scripts here
    if not draft.get("ok", True) and draft.get("error"):
        findings.append({"severity": "high", "msg": f"draft error: {draft.get('error')}"})
        ok = False
    body = draft.get("json") or {}
    if isinstance(body, dict):
        if body.get("ok") is False:
            findings.append({"severity": "high", "msg": "draft reported ok=false"})
            ok = False
        # Prefer provenance / evidence when present
        if "verification" in body and body["verification"].get("ok") is False:
            findings.append({"severity": "medium", "msg": "verification not ok in draft"})
            ok = False
    if not findings:
        findings.append({"severity": "info", "msg": "no structural issues in draft artefact"})
    return {
        "ok": ok,
        "tools_used": [],
        "isolated": True,
        "task": task,
        "findings": findings,
        "role": "critic_readonly",
    }


def execute(
    *,
    task: str = "",
    high_risk: bool = False,
    multi_constraint: bool = False,
    throwaway: bool = False,
    regulated: bool = False,
    dry_rails: bool = False,
) -> dict:
    plan_wrap = build_route(
        task=task,
        high_risk=high_risk,
        multi_constraint=multi_constraint,
        throwaway=throwaway,
        regulated=regulated,
    )
    if plan_wrap.get("missing_rails"):
        return {
            "ok": False,
            "status": "routing_invalid",
            "framework": "hydrafusion_execute",
            "plan": plan_wrap,
            "why": "validated_routing failed — missing rails",
            "accounting": {"legs_run": [], "cost_units_spent": 0},
            "ts": datetime.now(UTC).isoformat(),
        }

    plan = plan_wrap["plan"]
    pattern = plan["pattern"]
    ledger: list[dict] = []
    draft_result: dict = {}
    gate_passed = False
    critic_result: dict | None = None
    final_status = "running"
    accepted = False

    for leg in plan["legs"]:
        role = leg["role"]
        rail = leg["rail"]
        cost = int(leg.get("cost_units") or 1)
        timeout_s = int(leg.get("timeout_s") or 120)
        # Bound wall time in tests / CI: cap at 90s per leg for harness scripts
        timeout_s = min(timeout_s, 90 if dry_rails else timeout_s)

        entry = {
            "name": leg["name"],
            "role": role,
            "rail": rail,
            "cost_units": cost,
            "tools_allowed": leg.get("tools_allowed"),
            "started_at": datetime.now(UTC).isoformat(),
        }
        t0 = time.monotonic()

        if role == "critic":
            if leg.get("tools_allowed"):
                entry["result"] = {"ok": False, "error": "critic_must_be_tool_less"}
                entry["elapsed_s"] = round(time.monotonic() - t0, 3)
                ledger.append(entry)
                final_status = "rejected_principle_isolated_review"
                break
            entry["result"] = _critic_readonly(draft_result, task=task)
            critic_result = entry["result"]
        elif dry_rails:
            # Deterministic stub for unit tests — still exercises control flow
            if role in {"gate", "validator"}:
                entry["result"] = {"ok": True, "json": {"ok": True, "dry": True}}
                if role == "gate":
                    gate_passed = True
            elif role == "escalation":
                entry["result"] = {"ok": True, "json": {"ok": True, "escalated": True, "dry": True}}
            else:
                entry["result"] = {"ok": True, "json": {"ok": True, "dry": True, "role": role}}
                if role == "drafter":
                    draft_result = entry["result"]
        else:
            script = leg.get("script")
            args: list[str] = []
            if rail == "verify_complete":
                args = []  # script default suite
            elif rail == "goal_backward":
                args = ["--goal", "harness"]
            elif rail == "ralph_tick" or rail == "revision":
                # Prefer integrated observe without writing state spam
                script = "scripts/ralph_gsd_integrated_tick.py"
                args = ["--no-log", "--no-write-state"]
            entry["result"] = _run_rail(script, *args, timeout_s=timeout_s)
            if role == "drafter":
                draft_result = entry["result"]
            if role == "gate":
                j = (entry["result"].get("json") or {}) if isinstance(entry["result"], dict) else {}
                gate_passed = bool(entry["result"].get("ok")) and j.get("ok", True) is not False

        entry["elapsed_s"] = round(time.monotonic() - t0, 3)
        ledger.append(entry)

        # Cascade early exit: gate passed → skip escalation
        if pattern == "cascade" and role == "gate" and gate_passed:
            final_status = "accepted_cascade_early_exit"
            accepted = True
            break

        # Fail-safe: gate/validator hard fail → reject (no silent apply)
        if role in {"gate", "validator"} and not (entry["result"] or {}).get("ok"):
            final_status = "rejected_fail_safe"
            accepted = False
            break

        if role == "validator" and (entry["result"] or {}).get("ok"):
            final_status = "accepted_critique"
            accepted = True

        if pattern == "single" and role == "executor":
            accepted = bool((entry["result"] or {}).get("ok"))
            final_status = "accepted_single" if accepted else "rejected_single"

    spent = sum(e["cost_units"] for e in ledger)
    planned = int(plan.get("estimated_cost_units") or spent)
    return {
        "ok": accepted,
        "status": final_status,
        "framework": "hydrafusion_execute",
        "stolen_format": (
            "GitHub HydraFusion execute — Cascade early-exit + Critique isolation "
            "(InfoQ; not Copilot /experimental)"
        ),
        "source": {"infoq": "https://www.infoq.com/news/2026/09/github-hydrafusion/"},
        "pattern": pattern,
        "task": task,
        "plan": plan_wrap,
        "critic": critic_result,
        "accounting": {
            "legs_run": [
                {
                    "name": e["name"],
                    "role": e["role"],
                    "cost_units": e["cost_units"],
                    "elapsed_s": e["elapsed_s"],
                    "ok": (e.get("result") or {}).get("ok"),
                }
                for e in ledger
            ],
            "cost_units_spent": spent,
            "cost_units_planned": planned,
            "saved_vs_full_plan": max(0, planned - spent),
            "cascade_early_exit": final_status == "accepted_cascade_early_exit",
        },
        "principles_enforced": [
            "complete_accounting",
            "bounded_execution",
            "isolated_review",
            "fail_safe_apply",
            "validated_routing",
        ],
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", default="ops residual")
    p.add_argument("--high-risk", action="store_true")
    p.add_argument("--multi-constraint", action="store_true")
    p.add_argument("--throwaway", action="store_true")
    p.add_argument("--regulated", action="store_true")
    p.add_argument(
        "--dry-rails",
        action="store_true",
        help="Deterministic control-flow only (CI/unit); no heavy subprocess rails",
    )
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = execute(
        task=args.task,
        high_risk=args.high_risk,
        multi_constraint=args.multi_constraint,
        throwaway=args.throwaway,
        regulated=args.regulated,
        dry_rails=args.dry_rails,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
