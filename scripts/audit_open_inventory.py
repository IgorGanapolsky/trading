#!/usr/bin/env python3
"""Audit open option inventory vs ic_entries + 1-lot validation rules.

Exit codes:
  0 — clean (or no option positions)
  2 — unclean inventory (block new entries)
  1 — script/IO error

Usage:
  python scripts/audit_open_inventory.py
  python scripts/audit_open_inventory.py --json-out data/audit/open_inventory_latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap() -> Path:
    root = Path(__file__).resolve().parents[1]
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    return root


def main() -> int:
    root = _bootstrap()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(root))
    parser.add_argument(
        "--json-out",
        default="data/audit/open_inventory_latest.json",
        help="Write full audit JSON here",
    )
    args = parser.parse_args()

    try:
        from src.core.trading_constants import (
            MAX_CONCURRENT_IRON_CONDORS,
            MAX_CONTRACTS_PER_TRADE,
        )
    except Exception:
        MAX_CONTRACTS_PER_TRADE = 1
        MAX_CONCURRENT_IRON_CONDORS = 2

    from src.risk.open_inventory_audit import audit_from_files, write_audit_report

    result = audit_from_files(
        args.repo_root,
        max_contracts_per_trade=float(MAX_CONTRACTS_PER_TRADE),
        max_concurrent_iron_condors=int(MAX_CONCURRENT_IRON_CONDORS),
    )
    out_path = Path(args.repo_root) / args.json_out
    write_audit_report(result, out_path)

    print(json.dumps(result.to_dict(), indent=2))
    print(f"json_out={out_path}")
    print(f"clean={result.clean} findings={len(result.findings)}")

    if not result.clean:
        print("UNCLEAN_INVENTORY: block new validation entries until book matches journal")
        for reason in result.block_reasons():
            print(f"  - {reason}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
