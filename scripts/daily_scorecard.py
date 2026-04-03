#!/usr/bin/env python3
"""CLI wrapper for the direct daily trading scorecard."""

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

from src.analytics.daily_scorecard import write_daily_scorecard_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build direct Alpaca daily scorecard artifacts.")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root containing data/ and src/."
    )
    parser.add_argument(
        "--json-out",
        default="artifacts/daily_scorecard/latest_daily_scorecard.json",
        help="JSON artifact path.",
    )
    parser.add_argument(
        "--markdown-out",
        default="artifacts/daily_scorecard/latest_daily_scorecard.md",
        help="Markdown artifact path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root)
    scorecard = write_daily_scorecard_artifacts(
        repo_root,
        json_out=Path(args.json_out),
        markdown_out=Path(args.markdown_out),
    )
    print(json.dumps(scorecard, indent=2))
    print(f"json_out={Path(args.json_out)}")
    print(f"markdown_out={Path(args.markdown_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
