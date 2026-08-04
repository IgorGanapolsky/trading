#!/usr/bin/env python3
"""Fail when a closed structure in the active strategy family has no journaled exit path.

Why this exists (LL-361): 154 of 164 trades in the ledger carry no `exit_reason`, so the
realized loss on the killed iron-condor cohort can never be attributed to a stop, a
profit target, or a time exit. That data is gone. This guard makes sure the successor
strategy does not repeat it.

The historical cohort is not repairable, so it is not the gate. The gate is: every
**newly closed** structure in the active family must record how it was closed. Legacy
rows are reported for visibility and explicitly excluded from the pass/fail decision.

    python scripts/check_exit_reason_coverage.py           # exit 1 on any violation
    python scripts/check_exit_reason_coverage.py --json    # machine-readable
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADES_PATH = PROJECT_ROOT / "data" / "trades.json"
JOURNAL_PATH = PROJECT_ROOT / "data" / "put_credit_entries.json"

# Families whose historical rows predate exit-reason journaling. These are frozen
# evidence, not a backlog to fix -- excluded from the gate, still reported.
LEGACY_FAMILIES = {"iron_condor", "ic_simple"}

CLOSED_STATUSES = {"closed", "exit_filled"}


def _load(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def _family(row: dict) -> str:
    return row.get("strategy") or row.get("strategy_family") or "unknown"


def collect() -> dict[str, Any]:
    """Return coverage stats plus the list of gate violations."""
    ledger = _load(TRADES_PATH)
    trades = ledger.get("trades", []) if isinstance(ledger, dict) else []

    journal = _load(JOURNAL_PATH)
    journal_rows = [
        {**entry, "id": key}
        for key, entry in (journal.items() if isinstance(journal, dict) else [])
    ]

    rows: list[tuple[str, dict]] = [("ledger", r) for r in trades]
    rows += [("journal", r) for r in journal_rows]

    total = 0
    recorded = 0
    legacy_missing = 0
    violations: list[dict[str, str]] = []

    for source, row in rows:
        status = str(row.get("status", "")).lower()
        # Journal rows are lifecycle records; only graded once actually closed.
        if source == "journal" and status not in CLOSED_STATUSES:
            continue

        total += 1
        family = _family(row)
        has_reason = bool(row.get("exit_reason"))
        if has_reason:
            recorded += 1
            continue

        if family in LEGACY_FAMILIES:
            legacy_missing += 1
            continue

        violations.append(
            {
                "id": str(row.get("id", "<no id>")),
                "source": source,
                "strategy": family,
                "status": status or "<none>",
            }
        )

    return {
        "total_closed": total,
        "exit_reason_recorded": recorded,
        "coverage": round(recorded / total, 4) if total else None,
        "legacy_missing": legacy_missing,
        "legacy_families": sorted(LEGACY_FAMILIES),
        "violations": violations,
        "passed": not violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args()

    report = collect()

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1

    coverage = report["coverage"]
    coverage_str = f"{coverage:.1%}" if coverage is not None else "n/a"
    print(f"Closed structures graded : {report['total_closed']}")
    print(f"Exit reason recorded     : {report['exit_reason_recorded']} ({coverage_str})")
    print(f"Legacy rows without one  : {report['legacy_missing']} (excluded from gate; LL-361)")

    if report["violations"]:
        print(f"\nFAIL: {len(report['violations'])} active-family close(s) with no exit_reason:")
        for violation in report["violations"]:
            print(
                f"  - {violation['id']} [{violation['source']}]"
                f" strategy={violation['strategy']} status={violation['status']}"
            )
        print("\nA close without a journaled exit path cannot be attributed later.")
        return 1

    print("\nPASS: every active-family close journals an exit path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
