#!/usr/bin/env python3
"""Report whether the incumbent should trade and which broker can support a pivot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.safety.strategy_pivot import build_pivot_report

DEFAULT_STATE = Path("data/system_state.json")
DEFAULT_TRADES = Path("data/trades.json")
DEFAULT_ENTRIES = Path("data/ic_entries.json")
DEFAULT_TOURNAMENT = Path("config/strategy_candidate_tournament.json")
DEFAULT_BROKER = Path("data/audit/clearstreet_active_capability_20260722.json")
DEFAULT_INVENTORY = Path("data/audit/open_inventory_latest.json")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate strategy edge, ledger integrity, and broker compatibility."
    )
    parser.add_argument("--system-state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("--tournament", type=Path, default=DEFAULT_TOURNAMENT)
    parser.add_argument("--broker", type=Path, default=DEFAULT_BROKER)
    parser.add_argument("--inventory-audit", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--json", action="store_true", help="Print the complete JSON report.")
    return parser.parse_args()


def _print_human(report: dict[str, Any]) -> None:
    north_star = report["north_star"]
    incumbent = report["incumbent"]
    decision = incumbent["decision"]
    audit = incumbent["ledger_audit"]
    broker = report["broker"]
    inventory = report["operational_inventory"]

    print("STRATEGY PIVOT GATE")
    print(f"System action: {report['system_action']}")
    print(f"Research action: {report['research_action']}")
    print(f"North Star on course: {north_star['on_course']}")
    print(
        f"Paper equity: ${north_star['current_equity']:,.2f} "
        f"({north_star['total_pl']:+,.2f}, drawdown {north_star['drawdown_pct']:.2f}%)"
    )
    print(f"Incumbent: {incumbent['strategy_id']} -> {decision['status']}")
    print(f"May open new positions: {decision['may_open_new_positions']}")
    print(f"May manage existing positions: {decision['may_manage_existing_positions']}")
    print(f"Ledger clean: {audit['clean']}")
    print(
        f"Operational broker inventory clean: {inventory['clean']} "
        f"(authority={inventory['authority']})"
    )
    for reason in decision["reasons"]:
        print(f"  - {reason}")
    print(f"Clear Street role: {broker['current_role']}")
    print()
    print("Candidate tournament:")
    for candidate in report["candidates"]:
        candidate_decision = candidate["decision"]
        broker_assessment = candidate["broker_assessment"]
        print(
            f"  - {candidate['strategy_id']}: {candidate_decision['status']}; "
            f"Clear Street execution eligible={broker_assessment['execution_eligible']}"
        )
        for blocker in broker_assessment["blockers"]:
            print(f"      broker blocker: {blocker}")


def main() -> int:
    args = parse_args()
    report = build_pivot_report(
        _load_json(args.system_state),
        _load_json(args.trades),
        _load_json(args.entries),
        _load_json(args.tournament),
        _load_json(args.broker),
        _load_json(args.inventory_audit),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report["north_star"]["on_course"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
