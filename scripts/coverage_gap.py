#!/usr/bin/env python3
"""VS 'Today I will improve test coverage' FORMAT steal.

Source: https://devblogs.microsoft.com/visualstudio/today-i-will-improve-test-coverage/

1. Measure a baseline before writing tests.
2. Rank real gaps (skip no-behavior files: enums/constants).
3. Re-measure the *same scope* after — not a new global percentage.

Do not clone Visual Studio Test Agent or Copilot `@test #solution`.
Do not claim repo-wide 100% coverage. Global 100% is not a promotion gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://devblogs.microsoft.com/visualstudio/today-i-will-improve-test-coverage/"
REFUSES = (
    "do_not_clone_vs_test_agent",
    "do_not_claim_repo_wide_100_percent",
    "tests_for_the_sake_of_tests_are_refused",
    "remeasure_same_scope_only",
)


def load_coverage(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    totals = data.get("totals") or {}
    return {"files": files, "totals": totals}


def _percent(entry: dict[str, Any]) -> float | None:
    summary = entry.get("summary") if isinstance(entry, dict) else None
    if not isinstance(summary, dict):
        return None
    val = summary.get("percent_covered")
    if isinstance(val, (int, float)):
        return float(val)
    return None


def is_no_behavior(text: str) -> bool:
    """Skip files with no executable units (enums, constants, empty)."""
    if re.search(r"^\s*(async\s+)?def\s+", text, re.M):
        return False
    if re.search(r"^\s*class\s+\w+\s*\([^)]*\bEnum\b", text, re.M):
        return True
    return not (
        re.search(r"^\s*class\s+", text, re.M) and re.search(r"^\s+def\s+", text, re.M)
    )


def baseline(
    cov: dict[str, Any],
    *,
    floor: float = 50.0,
    scope: str = "",
    source_root: Path | None = None,
) -> dict[str, Any]:
    gaps = []
    skipped = []
    scoped = []
    files = cov.get("files") or {}
    for path, entry in sorted(files.items()):
        if scope and scope not in path.replace("\\", "/"):
            continue
        scoped.append(path)
        pct = _percent(entry)
        src = (source_root or ROOT) / path if not Path(path).is_absolute() else Path(path)
        if src.exists():
            try:
                text = src.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = "def _present():\n    pass\n"
            if is_no_behavior(text):
                skipped.append({"path": path, "reason": "no_behavior"})
                continue
        if pct is None or pct < floor:
            gaps.append({"path": path, "percent_covered": pct, "floor": floor})
    totals = (cov.get("totals") or {}).get("percent_covered")
    return {
        "ok": True,
        "framework": "coverage_gap",
        "stolen_format": (
            "Aaron Powell / VS: baseline coverage before writing tests; "
            "target real gaps; skip files with nothing to test; remeasure same scope"
        ),
        "source": SOURCE,
        "n_scoped": len(scoped),
        "n_gaps": len(gaps),
        "gaps": gaps,
        "skipped_no_behavior": skipped,
        "totals_percent_covered": totals,
        "global_100_is_not_a_gate": True,
        "refuses": list(REFUSES),
    }


def compare(before: dict[str, Any], after: dict[str, Any], *, scope: str = "") -> dict[str, Any]:
    b_files = before.get("files") or {}
    a_files = after.get("files") or {}
    keys = sorted(set(b_files) | set(a_files))
    if scope:
        keys = [k for k in keys if scope in k.replace("\\", "/")]
    deltas = []
    improved = 0
    regressed = 0
    for path in keys:
        bp = _percent(b_files.get(path) or {})
        ap = _percent(a_files.get(path) or {})
        if bp is None and ap is None:
            continue
        delta = None
        if bp is not None and ap is not None:
            delta = ap - bp
            if delta > 0:
                improved += 1
            elif delta < 0:
                regressed += 1
        deltas.append({"path": path, "before": bp, "after": ap, "delta": delta})
    return {
        "ok": regressed == 0,
        "n_compared": len(deltas),
        "n_improved": improved,
        "n_regressed": regressed,
        "deltas": deltas,
        "same_scope": scope or "*",
        "global_100_is_not_a_gate": True,
        "refuses": list(REFUSES),
        "source": SOURCE,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline", help="rank gaps from coverage.json")
    b.add_argument("--json", dest="cov", required=True, type=Path)
    b.add_argument("--floor", type=float, default=50.0)
    b.add_argument("--scope", default="")
    c = sub.add_parser("compare", help="same-scope before vs after")
    c.add_argument("--before", required=True, type=Path)
    c.add_argument("--after", required=True, type=Path)
    c.add_argument("--scope", default="")
    c.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "baseline":
        report = baseline(load_coverage(args.cov), floor=args.floor, scope=args.scope)
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    report = compare(load_coverage(args.before), load_coverage(args.after), scope=args.scope)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if args.strict and not report["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
