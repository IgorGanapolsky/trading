#!/usr/bin/env python3
"""Validation factory tick — maximize clean put-credit cadence toward n=30.

In-process desk ritual optimized for sample velocity without rule drift:
  1) production gate
  2) inventory audit
  3) put-credit status + dry-run plan
  4) residual IC dry-run (exit-only)
  5) cohort + world-class scorecards

Never opens live risk. Paper entry only with --execute-if-clear.
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

OUT = ROOT / "data" / "audit" / "validation_factory_latest.json"


def _call(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = fn()
        rc = 0
        if isinstance(result, int):
            rc = result
        elif isinstance(result, bool):
            rc = 0 if result else 1
        return {
            "step": name,
            "ok": rc == 0,
            "returncode": rc,
            "result": result if not isinstance(result, (int, bool)) else None,
        }
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return {"step": name, "ok": code == 0, "returncode": code}
    except Exception as exc:  # noqa: BLE001
        return {
            "step": name,
            "ok": False,
            "returncode": 99,
            "error": str(exc),
            "traceback": traceback.format_exc()[-1200:],
        }


def _run_module_main(module_path: str, argv: list[str]) -> int:
    import importlib.util

    path = ROOT / module_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_path}")
    mod = importlib.util.module_from_spec(spec)
    old = sys.argv[:]
    try:
        sys.argv = [str(path), *argv]
        spec.loader.exec_module(mod)
        if hasattr(mod, "main") and callable(mod.main):
            out = mod.main()
            return int(out) if out is not None else 0
        return 0
    finally:
        sys.argv = old


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-if-clear",
        action="store_true",
        help="Paper put-credit entry if production gate allows (never live)",
    )
    parser.add_argument("--skip-sync", action="store_true")
    args = parser.parse_args()

    steps: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": "validation-factory-tick/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "goal": "n>=30 clean spy_put_credit closes with expectancy>0 and PF>1",
        "steps": steps,
    }

    if not args.skip_sync:
        steps.append(
            _call("sync_alpaca_state", lambda: _run_module_main("scripts/sync_alpaca_state.py", []))
        )

    steps.append(
        _call(
            "audit_open_inventory",
            lambda: _run_module_main("scripts/audit_open_inventory.py", []),
        )
    )

    from src.risk.production_gate import evaluate_production_gate

    gate = evaluate_production_gate(for_live=False)
    report["production_gate"] = gate.to_dict()
    steps.append(
        {
            "step": "production_gate",
            "ok": gate.allow_new_risk,
            "allow_new_risk": gate.allow_new_risk,
            "grade": gate.grade,
            "blockers": gate.blockers,
        }
    )

    steps.append(
        _call(
            "spy_put_credit_status",
            lambda: _run_module_main("scripts/spy_put_credit.py", ["--status"]),
        )
    )
    steps.append(
        _call(
            "spy_put_credit_dry_run",
            lambda: _run_module_main("scripts/spy_put_credit.py", ["--dry-run"]),
        )
    )
    steps.append(
        _call(
            "residual_ic_manager_dry_run",
            lambda: _run_module_main("scripts/residual_ic_manager.py", ["--dry-run"]),
        )
    )

    executed = False
    if args.execute_if_clear and gate.allow_new_risk:
        steps.append(
            _call(
                "spy_put_credit_paper_entry",
                lambda: _run_module_main("scripts/spy_put_credit.py", []),
            )
        )
        executed = bool(steps[-1].get("ok"))
    elif args.execute_if_clear:
        steps.append(
            {
                "step": "spy_put_credit_paper_entry",
                "ok": False,
                "skipped": True,
                "reason": f"gate blocked: {gate.blockers}",
            }
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

    report["executed_paper_entry"] = executed
    report["all_ok"] = all(bool(s.get("ok", True)) for s in steps if not s.get("skipped"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"validation_factory_tick written: {OUT}")
    print(f"allow_new_risk={gate.allow_new_risk} grade={gate.grade} executed={executed}")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
