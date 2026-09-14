#!/usr/bin/env python3
"""BMAD implementation-readiness FORMAT (SaM BMAD guide — not bmad-method install).

Validates SPEC.md five-element contract + proportional planning depth +
traceability to constitution/converge/verify. Append-only gaps → .planning/tasks.md.

EXIT 0 always unless --strict (then 2 when not ready).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404 — fixed argv only
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "SPEC.md"
CONSTITUTION = ROOT / "docs" / "CONSTITUTION.md"
PLANNING = ROOT / ".planning"
TASKS = PLANNING / "tasks.md"

REQUIRED_SECTIONS = (
    ("why", re.compile(r"^## Why\b", re.M)),
    ("capabilities", re.compile(r"^## Capabilities", re.M)),
    ("constraints", re.compile(r"^## Constraints\b", re.M)),
    ("non_goals", re.compile(r"^## Non-goals\b", re.M)),
    ("success_signal", re.compile(r"^## Success signal\b", re.M)),
)


def parse_planning_depth(text: str) -> str:
    m = re.search(r"\*\*Planning depth:\*\*\s*(.+)", text)
    if m:
        return m.group(1).strip()
    if re.search(r"Quick Flow", text, re.I):
        return "quick_flow"
    return "unknown"


def validate_spec(text: str) -> list[dict]:
    checks = []
    if not text.strip():
        return [{"id": "spec:file", "ok": False, "error": "empty"}]
    for name, pat in REQUIRED_SECTIONS:
        checks.append({"id": f"spec:{name}", "ok": bool(pat.search(text))})
    # Capabilities need at least one success condition marker
    checks.append(
        {
            "id": "spec:success_conditions",
            "ok": "Success condition" in text or "success condition" in text.lower(),
        }
    )
    # Non-goals must refuse commercial A+ theater
    checks.append(
        {
            "id": "spec:non_goal_aplus_theater",
            "ok": "fee-yes" in text.lower() or "overall a+" in text.lower(),
        }
    )
    return checks


def _run_json(argv: list[str], timeout: int = 180) -> dict:
    r = subprocess.run(  # nosec B603
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        data = {"ok": False, "error": "parse", "stderr": (r.stderr or "")[:400]}
    data["_exit"] = r.returncode
    return data


def readiness(*, append_tasks: bool = True, verify_live: bool = False) -> dict:
    spec_text = SPEC.read_text() if SPEC.exists() else ""
    spec_checks = validate_spec(spec_text)
    if not SPEC.exists():
        spec_checks = [{"id": "spec:file", "ok": False, "error": f"missing {SPEC}"}]

    depth = parse_planning_depth(spec_text)
    constitution_ok = CONSTITUTION.exists() and "Cash Truth" in CONSTITUTION.read_text()

    converge_argv = [sys.executable, str(ROOT / "scripts" / "speckit_converge.py"), "--no-append"]
    if verify_live:
        converge_argv.append("--verify-live")
    converge = _run_json(converge_argv)
    scope = _run_json([sys.executable, str(ROOT / "scripts" / "audit_active_scope.py"), "--json"])

    checks = [
        *spec_checks,
        {"id": "constitution_present", "ok": constitution_ok},
        {
            "id": "converge_harness",
            "ok": converge.get("status") == "converged",
            "status": converge.get("status"),
        },
        {"id": "active_scope", "ok": bool(scope.get("ok"))},
        {
            "id": "planning_depth_declared",
            "ok": depth != "unknown",
            "depth": depth,
        },
    ]

    gaps = [c for c in checks if not c.get("ok")]
    remaining = []
    for g in gaps:
        remaining.append(
            {
                "id": f"BMAD-{g['id']}",
                "title": f"Readiness gap: {g['id']} — fix before implement expands",
                "phase": "readiness",
            }
        )

    # BMAD Quick Flow: harness-ready when SPEC valid + converge + scope
    # even if cash ship_lock stands
    ready = len(gaps) == 0
    status = "ready" if ready else "not_ready"

    if append_tasks and remaining:
        PLANNING.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).isoformat()
        block = [
            "",
            f"## Phase BMAD Readiness — {ts}",
            "",
            "Append-only (BMAD readiness FORMAT).",
            "",
        ]
        for t in remaining:
            block.append(f"- [ ] {t['id']}: {t['title']}")
        block.append("")
        with TASKS.open("a", encoding="utf-8") as fh:
            if not TASKS.exists() or TASKS.stat().st_size == 0:
                fh.write("# tasks.md\n")
            fh.write("\n".join(block))

    return {
        "ok": True,
        "framework": "bmad_readiness",
        "stolen_format": "BMAD SPEC.md + readiness gate (SaM guide; not bmad-method)",
        "status": status,
        "ready": ready,
        "planning_depth": depth,
        "quick_flow_allowed": "quick" in depth.lower(),
        "spec": str(SPEC),
        "checks": checks,
        "remaining_tasks": remaining,
        "ship_lock": (converge.get("ship_lock") or []),
        "overall_letter": converge.get("overall_letter"),
        "cash_ok": converge.get("cash_ok"),
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verify-live", action="store_true")
    parser.add_argument("--no-append", action="store_true")
    args = parser.parse_args(argv)
    out = readiness(append_tasks=not args.no_append, verify_live=args.verify_live)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("ready"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
