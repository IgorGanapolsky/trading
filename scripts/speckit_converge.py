#!/usr/bin/env python3
"""Spec Kit converge FORMAT for trading (github/spec-kit — not a specify-cli install).

Assess present state vs constitution + STATE residual + verify evidence.
Append remaining work to `.planning/tasks.md` (append-only).
Print JSON: status=converged|gaps_found + remaining_tasks.

EXIT 0 always unless --strict (then 2 on gaps_found).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess  # nosec B404 — fixed argv only (audit_active_scope)
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION = ROOT / "docs" / "CONSTITUTION.md"
PLANNING = ROOT / ".planning"
STATE_MD = PLANNING / "STATE.md"
TASKS_MD = PLANNING / "tasks.md"
TICK = ROOT / "scripts" / "ralph_gsd_tick.py"


def _load_tick():
    spec = importlib.util.spec_from_file_location("ralph_gsd_tick", TICK)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {TICK}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse_state_residual(text: str) -> str | None:
    m = re.search(r"^residual:\s*(\S+)", text, re.M)
    if m:
        return m.group(1).strip().strip('"')
    m = re.search(r"\*\*Residual:\*\*\s*`([^`]+)`", text)
    return m.group(1) if m else None


def _constitution_checks(text: str) -> list[dict]:
    """Fail-closed presence checks for binding principles."""
    required = [
        ("I. Cash Truth", "Cash Truth Before Grades"),
        ("II. Paper Lab", "Paper Lab Scope"),
        ("III. Test-Backed", "Test-Backed Change"),
        ("IV. Spec pipeline", "Spec → Plan → Tasks → Implement → Converge"),
        ("V. Anti-Babysitting", "Anti-Babysitting Autonomy"),
        ("fee-yes lock", "fee-yes"),
        ("live_blocked", "live_blocked"),
    ]
    out = []
    for cid, needle in required:
        ok = needle in text
        out.append({"id": f"constitution:{cid}", "ok": ok, "needle": needle})
    return out


def _active_scope_ok() -> dict:
    script = ROOT / "scripts" / "audit_active_scope.py"
    if not script.exists():
        return {"id": "active_scope", "ok": False, "error": "audit_active_scope.py missing"}

    r = subprocess.run(  # nosec B603 — no shell; argv list only
        [sys.executable, str(script), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "id": "active_scope",
            "ok": False,
            "error": "parse",
            "stderr": (r.stderr or "")[:300],
        }
    # Prefer explicit ok/pass fields when present
    ok = bool(data.get("ok") is True or data.get("pass") is True or data.get("clean") is True)
    if "violations" in data:
        ok = ok or (not data.get("violations"))
    if "status" in data and isinstance(data["status"], str):
        ok = ok or data["status"].lower() in {"ok", "pass", "clean", "compliant"}
    return {"id": "active_scope", "ok": ok, "raw_keys": sorted(data.keys())[:12]}


def converge(*, verify_live: bool = False, append_tasks: bool = True) -> dict:
    tick = _load_tick()
    score = tick._scorecard()
    prs = tick._open_prs()
    pick = tick._pick(score if "error" not in score else {}, prs)
    phase = tick._phase_loop(pick)
    verification = tick.verify_evidence(pick, live_checkout=verify_live)

    constitution_text = CONSTITUTION.read_text() if CONSTITUTION.exists() else ""
    const_checks = _constitution_checks(constitution_text)
    if not CONSTITUTION.exists():
        const_checks = [
            {
                "id": "constitution:file",
                "ok": False,
                "error": f"missing {CONSTITUTION}",
            }
        ]

    state_residual = None
    if STATE_MD.exists():
        state_residual = _parse_state_residual(STATE_MD.read_text())

    scope = _active_scope_ok()
    overall = (score.get("overall") or {}).get("letter")
    cash_ok = bool((score.get("cash_fee_yes") or {}).get("ok"))

    # Constitution ship gate: never "converged" for overall A+ while cash F
    grade_gate = {
        "id": "grade_honesty",
        "ok": True,
        "overall": overall,
        "cash_ok": cash_ok,
        "note": "overall F expected until fee-yes; claiming A+ would fail",
    }
    if overall in {"A", "A+", "A-"} and not cash_ok:
        grade_gate["ok"] = False
        grade_gate["note"] = "constitution I violation: overall A* while cash unmet"

    checks = [
        *const_checks,
        scope,
        grade_gate,
        {
            "id": "verify_residual",
            "ok": bool(verification.get("ok")),
            "status": verification.get("status"),
            "residual": pick.get("residual"),
        },
        {
            "id": "state_align",
            "ok": (state_residual is None) or (state_residual == pick.get("residual")),
            "state_residual": state_residual,
            "pick_residual": pick.get("residual"),
        },
    ]

    remaining: list[dict] = []
    if not all(c.get("ok") for c in const_checks):
        remaining.append(
            {
                "id": "C-CONST-001",
                "title": "Restore missing constitution principles in docs/CONSTITUTION.md",
                "phase": "convergence",
            }
        )
    if not scope.get("ok"):
        remaining.append(
            {
                "id": "C-SCOPE-001",
                "title": "Heal active scope (audit_active_scope.py --json must pass)",
                "phase": "convergence",
            }
        )
    if not verification.get("ok"):
        residual = pick.get("residual")
        remaining.append(
            {
                "id": f"C-VERIFY-{residual}",
                "title": f"Satisfy verify gate for residual `{residual}`: {pick.get('act')}",
                "phase": "convergence",
            }
        )
    if not cash_ok:
        remaining.append(
            {
                "id": "C-CASH-001",
                "title": "Fee-yes: prepaid Miramar ≥$100 Stripe non-owner + clerk_image_ok (ship lock)",
                "phase": "convergence",
                "blocks_overall_aplus": True,
            }
        )
    if pick.get("residual") == "fix_required_ci":
        remaining.append(
            {
                "id": "C-CI-001",
                "title": "Heal required CI (assess→fix→test); re-arm auto-merge",
                "phase": "convergence",
            }
        )

    # Spec Kit: Converged when constitution + scope + residual verify + state
    # align + grade honesty. Cash fee-yes is ship_lock (standing), not alone a
    # harness gaps_found when operational verify passed.
    harness_ids = {c["id"] for c in const_checks} | {
        "active_scope",
        "grade_honesty",
        "verify_residual",
        "state_align",
    }
    harness_ok = all(c["ok"] for c in checks if c["id"] in harness_ids)

    ship_lock = [t for t in remaining if t.get("blocks_overall_aplus")]
    implement_now = [t for t in remaining if not t.get("blocks_overall_aplus")]

    status = "converged" if harness_ok and not implement_now else "gaps_found"

    if append_tasks and implement_now:
        PLANNING.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).isoformat()
        lines = [
            "",
            f"## Phase Convergence — {ts}",
            "",
            "Append-only (Spec Kit converge FORMAT). Do not rewrite prior tasks.",
            "",
        ]
        for t in implement_now:
            lines.append(f"- [ ] {t['id']}: {t['title']}")
        lines.append("")
        with TASKS_MD.open("a", encoding="utf-8") as fh:
            if not TASKS_MD.exists() or TASKS_MD.stat().st_size == 0:
                fh.write("# tasks.md — Spec Kit converge append-only\n")
            fh.write("\n".join(lines))

    # Always refresh STATE via tick writer for spine continuity
    tick.write_state(
        pick,
        phase,
        verification,
        overall=overall,
    )
    tick.write_context(pick, phase)

    return {
        "ok": True,
        "framework": "speckit_converge",
        "stolen_format": "github/spec-kit converge + constitution (not specify-cli)",
        "status": status,
        "ts": datetime.now(UTC).isoformat(),
        "pick": pick,
        "phase_loop": phase,
        "verification": verification,
        "checks": checks,
        "remaining_tasks": remaining,
        "implement_now": implement_now,
        "ship_lock": ship_lock,
        "constitution": str(CONSTITUTION),
        "tasks_md": str(TASKS_MD) if TASKS_MD.exists() else None,
        "overall_letter": overall,
        "cash_ok": cash_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verify-live", action="store_true")
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="Do not append Convergence section to .planning/tasks.md",
    )
    args = parser.parse_args(argv)
    out = converge(verify_live=args.verify_live, append_tasks=not args.no_append)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and out.get("status") != "converged":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
