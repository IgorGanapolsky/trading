#!/usr/bin/env python3
"""CLI: Dagster-Style Software-Defined Assets & Asset Checks for Trading Ops.

Source: https://docs.dagster.io/

Commands:
  --doctor               Run Dagster SDA & asset check compliance doctor
  --list-assets          List all declared Software-Defined Assets
  --materialize <asset>  Materialize specific asset and its upstream lineage
  --materialize-all      Materialize the complete asset graph
  --json                 Format output as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.dagster_asset_engine import (  # noqa: E402
    AssetKey,
    AssetMaterializationEngine,
    diagnose_dagster_engine,
    get_default_trading_asset_graph,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dagster-Style Software-Defined Assets & Asset Checks Engine"
    )
    parser.add_argument(
        "--doctor", action="store_true", help="Run Dagster engine doctor diagnostics"
    )
    parser.add_argument("--list-assets", action="store_true", help="List declared SDAs and checks")
    parser.add_argument(
        "--materialize",
        type=str,
        default="",
        help="Materialize target asset (e.g. options/put_credit_candidates)",
    )
    parser.add_argument("--materialize-all", action="store_true", help="Materialize all assets")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    if args.doctor:
        report = diagnose_dagster_engine(ROOT)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            status_str = "PASS" if report.ok else "FAIL"
            print(
                f"=== Dagster SDA Engine Doctor: {status_str} ({report.score}/{report.max_score}) ==="
            )
            for check, passed in report.checks.items():
                print(f"  [{'✓' if passed else '✗'}] {check}: {report.details.get(check, '')}")
            if report.failing:
                print(f"Failing checks: {', '.join(report.failing)}")
            print(f"Content hash: {report.content_hash}")
        return 0 if report.ok else 1

    graph = get_default_trading_asset_graph()

    if args.list_assets:
        assets_dict = {k.to_string(): a.to_dict() for k, a in graph.assets.items()}
        if args.json:
            print(json.dumps(assets_dict, indent=2))
        else:
            print("=== Declared Software-Defined Assets (SDAs) ===")
            for key_str, a in assets_dict.items():
                deps_str = ", ".join(a["deps"]) if a["deps"] else "(none - root)"
                checks_str = ", ".join(a["checks"]) if a["checks"] else "(none)"
                print(f"Asset: {key_str} [Group: {a['group_name']}]")
                print(f"  Description: {a['description']}")
                print(f"  Upstream Deps: {deps_str}")
                print(f"  Attached Checks: {checks_str}")
        return 0

    if args.materialize or args.materialize_all:
        engine = AssetMaterializationEngine(graph)
        target_keys = None
        if args.materialize:
            target_keys = [AssetKey.parse(args.materialize)]
        mats = engine.materialize(target_keys)
        out_dict = {k: v.to_dict() for k, v in mats.items()}
        if args.json:
            print(json.dumps(out_dict, indent=2))
        else:
            print("=== Asset Materialization Run ===")
            for key_str, mat in mats.items():
                status_icon = "✓" if mat.success else "✗"
                print(
                    f"[{status_icon}] {key_str} ({mat.duration_ms} ms) -> Hash: {mat.content_hash}"
                )
                if mat.blocked_by:
                    print(f"    Blocked by: {mat.blocked_by}")
                if mat.metadata:
                    print(f"    Metadata: {json.dumps(mat.metadata)}")
                for chk in mat.check_results:
                    chk_icon = "✓" if chk["passed"] else "✗"
                    print(f"    Check [{chk_icon}] {chk['check_name']}: {chk['description']}")
        all_passed = all(m.success for m in mats.values())
        return 0 if all_passed else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
