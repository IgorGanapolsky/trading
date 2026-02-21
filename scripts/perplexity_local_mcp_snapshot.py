#!/usr/bin/env python3
"""Expose a read-only local ops snapshot for Perplexity Local MCP command connectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.local_ops_snapshot import build_local_ops_snapshot, render_local_ops_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only local ops snapshot.")
    parser.add_argument(
        "--repo-root",
        default=str(PROJECT_ROOT),
        help="Repository root to read from.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    payload = build_local_ops_snapshot(repo_root)

    if args.format == "markdown":
        print(render_local_ops_markdown(payload))
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
