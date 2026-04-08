#!/usr/bin/env python3
"""CLI wrapper for the closed-trade setup audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_repo_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root


_bootstrap_repo_root()

from src.analytics.trade_setup_audit import (  # noqa: E402
    write_trade_setup_audit_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a setup-level audit from data/trades.json.")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root containing data/trades.json."
    )
    parser.add_argument(
        "--json-out",
        default="artifacts/trade_setup_audit/latest_trade_setup_audit.json",
        help="JSON artifact path.",
    )
    parser.add_argument(
        "--markdown-out",
        default="artifacts/trade_setup_audit/latest_trade_setup_audit.md",
        help="Markdown artifact path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = write_trade_setup_audit_artifacts(
        Path(args.repo_root),
        json_out=Path(args.json_out),
        markdown_out=Path(args.markdown_out),
    )
    print(json.dumps(audit, indent=2))
    print(f"json_out={Path(args.json_out)}")
    print(f"markdown_out={Path(args.markdown_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
