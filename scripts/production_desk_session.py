#!/usr/bin/env python3
"""World-class desk session: sync → audit → scorecards → production gate → dry-run.

Usage:
  python3 scripts/production_desk_session.py
  python3 scripts/production_desk_session.py --execute-if-clear   # paper entry only if gate green

Never deposits live capital. Live remains blocked until EDGE_CANDIDATE + kill switch flip.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "audit" / "production_desk_session_latest.json"


def _run(cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1000:],
            "ok": proc.returncode == 0,
        }
    except Exception as exc:  # noqa: BLE001
        return {"cmd": cmd, "returncode": 99, "ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-if-clear",
        action="store_true",
        help="If production gate allows new paper risk, run spy_put_credit entry (not dry-run)",
    )
    parser.add_argument("--skip-sync", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    steps: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": "production-desk-session/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "steps": steps,
    }

    if not args.skip_sync:
        steps.append(_run([py, "scripts/sync_alpaca_state.py"], timeout=300))

    steps.append(_run([py, "scripts/audit_open_inventory.py"]))
    steps.append(_run([py, "scripts/put_credit_cohort_scorecard.py"]))
    steps.append(_run([py, "scripts/world_class_production_scorecard.py"]))

    from src.risk.production_gate import evaluate_production_gate

    gate = evaluate_production_gate(for_live=False)
    report["production_gate"] = gate.to_dict()
    steps.append(
        {
            "cmd": ["evaluate_production_gate"],
            "ok": gate.allow_new_risk,
            "grade": gate.grade,
            "score_0_10": gate.score_0_10,
            "blockers": gate.blockers,
        }
    )

    # Always dry-run for visibility
    steps.append(_run([py, "scripts/spy_put_credit.py", "--dry-run", "--skip-production-gate"]))

    if args.execute_if_clear and gate.allow_new_risk:
        steps.append(_run([py, "scripts/spy_put_credit.py"]))  # paper entry path
    elif args.execute_if_clear:
        steps.append(
            {
                "cmd": ["spy_put_credit_execute"],
                "ok": False,
                "skipped": True,
                "reason": f"gate blocked: {gate.blockers}",
            }
        )

    report["summary"] = {
        "all_ok": all(s.get("ok", False) for s in steps if not s.get("skipped")),
        "allow_new_paper_risk": gate.allow_new_risk,
        "allow_live_capital": gate.allow_live_capital,
        "ops_grade": gate.grade,
        "ops_score": gate.score_0_10,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    print("=== PRODUCTION DESK SESSION ===")
    print(f"ops_grade={gate.grade} score={gate.score_0_10} allow_new_risk={gate.allow_new_risk}")
    print(f"blockers={gate.blockers}")
    for s in steps:
        cmd = s.get("cmd")
        print(f"  [{'OK' if s.get('ok') else 'FAIL'}] {cmd} rc={s.get('returncode', '-')}")
    print(f"json_out={OUT}")
    return 0 if gate.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
