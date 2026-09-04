#!/usr/bin/env python3
"""Package-manager honesty doctor. Always JSON. Never pnpm speedup claims."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ops.package_manager_honesty import (  # noqa: E402
    classify_command,
    lookalike_hits,
    scan_tree,
)

OPS = Path(__file__)


class _JsonArgParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        print(
            json.dumps(
                {"ok": False, "status": "UNAVAILABLE", "error": message}, indent=2, sort_keys=True
            )
        )
        self.exit(2)


def _parser() -> argparse.ArgumentParser:
    parser = _JsonArgParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--classify", default="", help="Install command to classify")
    parser.add_argument("--propose-switch", default="", help="Rejected unless uv/none")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.classify or args.propose_switch:
        scan = scan_tree(args.root)
        payload = classify_command(
            args.classify,
            has_uv_lock=bool(scan.get("uv_lock")),
            propose_switch=args.propose_switch or None,
        )
        payload["scan"] = {k: scan[k] for k in ("ok", "status", "canonical", "foreign_lockfiles")}
        print(json.dumps(payload, indent=2, sort_keys=True))
        # Dual/missing lockfile must fail the gate even if the command text looks frozen-uv.
        if not scan.get("ok"):
            return 2
        return 0 if payload.get("allowed") else 2

    payload = scan_tree(args.root)
    payload["lookalike_hits"] = lookalike_hits(OPS.read_text(encoding="utf-8"))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
