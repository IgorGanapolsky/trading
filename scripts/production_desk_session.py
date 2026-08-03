#!/usr/bin/env python3
"""World-class desk session: sync → audit → scorecards → production gate → dry-run.

Usage:
  python3 scripts/production_desk_session.py
  python3 scripts/production_desk_session.py --execute-if-clear   # paper entry only if gate green

Never deposits live capital. Live remains blocked until EDGE_CANDIDATE + kill switch flip.

Uses in-process imports (no subprocess) so bandit does not flag shell execution.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "audit" / "production_desk_session_latest.json"


def _call(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    """Run a desk step in-process; capture return code / exceptions."""
    try:
        result = fn()
        rc = 0
        if isinstance(result, int):
            rc = result
        elif isinstance(result, bool):
            rc = 0 if result else 1
        return {
            "cmd": [name],
            "returncode": rc,
            "ok": rc == 0,
            "result": result if not isinstance(result, int) else None,
        }
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return {"cmd": [name], "returncode": code, "ok": code == 0}
    except Exception as exc:  # noqa: BLE001
        return {
            "cmd": [name],
            "returncode": 99,
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc()[-1500:],
        }


def _run_module_main(module_path: str, argv: list[str]) -> int:
    """Import scripts/<module> and invoke main() with temporary argv."""
    import importlib.util

    path = ROOT / module_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_path}")
    mod = importlib.util.module_from_spec(spec)
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(path), *argv]
        spec.loader.exec_module(mod)
        if hasattr(mod, "main") and callable(mod.main):
            out = mod.main()
            return int(out) if out is not None else 0
        return 0
    finally:
        sys.argv = old_argv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-if-clear",
        action="store_true",
        help="If production gate allows new paper risk, run spy_put_credit entry (not dry-run)",
    )
    parser.add_argument("--skip-sync", action="store_true")
    args = parser.parse_args()

    steps: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": "production-desk-session/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "steps": steps,
    }

    if not args.skip_sync:
        steps.append(
            _call(
                "sync_alpaca_state",
                lambda: _run_module_main("scripts/sync_alpaca_state.py", []),
            )
        )

    steps.append(
        _call(
            "audit_open_inventory",
            lambda: _run_module_main("scripts/audit_open_inventory.py", []),
        )
    )
    steps.append(
        _call(
            "put_credit_cohort_scorecard",
            lambda: _run_module_main("scripts/put_credit_cohort_scorecard.py", []),
        )
    )
    steps.append(
        _call(
            "world_class_production_scorecard",
            lambda: _run_module_main("scripts/world_class_production_scorecard.py", []),
        )
    )

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
    steps.append(
        _call(
            "spy_put_credit --dry-run",
            lambda: _run_module_main(
                "scripts/spy_put_credit.py",
                ["--dry-run", "--skip-production-gate"],
            ),
        )
    )

    if args.execute_if_clear and gate.allow_new_risk:
        steps.append(
            _call(
                "spy_put_credit paper entry",
                lambda: _run_module_main("scripts/spy_put_credit.py", []),
            )
        )
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
