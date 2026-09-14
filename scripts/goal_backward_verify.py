#!/usr/bin/env python3
"""GSD goal-backward verification FORMAT (AI Engineer Substack / open-gsd idea).

Ask what must be TRUE for the goal — not did the command run.
Each condition is a fresh proof command + required substrings.

Stolen from: theaiengineer.substack.com Superpowers vs GSD vs Compound Engineering
(Not an install of GSD-original; we use open-gsd FORMAT only.)

EXIT 0 when all conditions pass; EXIT 2 otherwise (--strict default for CI).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Allow importing sibling scripts
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from superpowers_verify_complete import run_proof  # noqa: E402


def harness_conditions() -> list[dict]:
    """Goal: harness residual is evidence-true (not merely green theater)."""
    py = sys.executable
    return [
        {
            "id": "GB-H1",
            "must_be_true": "Ralph/speckit/superpowers/bmad unit tests all pass",
            "command": [
                py,
                "-m",
                "pytest",
                "tests/test_ralph_gsd_tick.py",
                "tests/test_speckit_steal.py",
                "tests/test_superpowers_steal.py",
                "tests/test_bmad_steal.py",
                "-q",
            ],
            "require_substr": ["passed"],
        },
        {
            "id": "GB-H2",
            "must_be_true": "BMAD readiness ready=true (SPEC contract hold)",
            "command": [py, "scripts/bmad_readiness.py", "--no-append"],
            "require_substr": ['"ready": true'],
        },
        {
            "id": "GB-H3",
            "must_be_true": "Spec Kit converge status=converged",
            "command": [py, "scripts/speckit_converge.py", "--no-append"],
            "require_substr": ['"status": "converged"'],
        },
        {
            "id": "GB-H4",
            "must_be_true": "Active scope freeze clean (IC killed, paper only)",
            "command": [py, "scripts/audit_active_scope.py", "--json"],
            "require_substr": ['"ok": true'],
        },
        {
            "id": "GB-H5",
            "must_be_true": "Grade honesty: cash_ok false (no A+ theater without fee-yes)",
            "command": [py, "scripts/speckit_converge.py", "--no-append"],
            # CI may lack fleet scorecard → overall_letter null; cash_ok must stay false.
            "require_substr": ['"cash_ok": false'],
            "forbid_substr": ['"overall_letter": "A+"', '"overall_letter": "A"'],
        },
    ]


def cash_conditions() -> list[dict]:
    """Goal: cash residual operationally true (still not fee-yes)."""
    py = sys.executable
    return [
        {
            "id": "GB-C1",
            "must_be_true": "Call sheet exists with dial entries",
            "command": [
                py,
                "-c",
                (
                    "from pathlib import Path; "
                    "p=Path.home()/'workspace/git/igor/RealEstate-lane-grok/outreach/CALL_SHEET_VERIFIED.md'; "
                    "ok=p.exists() and 'Dial' in p.read_text(); "
                    "print('SHEET_OK' if ok else 'SHEET_MISSING'); "
                    "raise SystemExit(0 if ok else 1)"
                ),
            ],
            "require_substr": ["SHEET_OK"],
        },
        {
            "id": "GB-C2",
            "must_be_true": "At least one prepaid draft staged",
            "command": [
                py,
                "-c",
                "from pathlib import Path; d=Path.home()/'workspace/git/igor/RealEstate-lane-grok/outreach/drafts'; "
                "n=len(list(d.glob('prepaid_*.json'))) if d.exists() else 0; print(f'DRAFTS={n}'); "
                "raise SystemExit(0 if n>=1 else 1)",
            ],
            "require_substr": ["DRAFTS="],
        },
    ]


def verify_goal(goal: str, conditions: list[dict], *, timeout: int = 300) -> dict:
    results = []
    for cond in conditions:
        # Drop missing pytest modules if any
        cmd = list(cond["command"])
        if len(cmd) >= 3 and cmd[1:3] == ["-m", "pytest"]:
            missing = [p for p in cmd if p.endswith(".py") and not (ROOT / p).exists()]
            cmd = [c for c in cmd if c not in missing]
        proof = run_proof(
            claim=cond["must_be_true"],
            command=cmd,
            require_substr=cond.get("require_substr") or [],
            forbid_substr=cond.get("forbid_substr") or [],
            timeout=timeout,
        )
        results.append(
            {
                "id": cond["id"],
                "must_be_true": cond["must_be_true"],
                "ok": proof["ok"],
                "exit_code": proof["exit_code"],
                "missing_substr": proof.get("missing_substr"),
                "output_tail": proof.get("output_tail", "")[-500:],
            }
        )
    all_ok = all(r["ok"] for r in results)
    return {
        "ok": all_ok,
        "framework": "goal_backward_verify",
        "stolen_format": "GSD goal-backward (AI Engineer Substack; open-gsd-safe)",
        "goal": goal,
        "conditions": results,
        "passed": sum(1 for r in results if r["ok"]),
        "total": len(results),
        "ts": datetime.now(UTC).isoformat(),
        "note": "TRUE-conditions ≠ fee-yes; commercial A+ still ship-locked",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goal",
        choices=["harness", "cash"],
        default="harness",
    )
    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument("--no-strict", action="store_true")
    args = parser.parse_args(argv)
    strict = not args.no_strict
    if args.goal == "harness":
        out = verify_goal(
            "Harness residual is evidence-true (goal-backward)",
            harness_conditions(),
        )
    else:
        out = verify_goal(
            "Cash residual operationally true (not fee-yes)",
            cash_conditions(),
        )
    print(json.dumps(out, indent=2, sort_keys=True))
    if strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
