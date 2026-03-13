#!/usr/bin/env python3
"""CLI wrapper for autonomous SQLite analytics builds."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.analytics.sqlite_analytics import (
    DEFAULT_DB_OUT,
    DEFAULT_SUMMARY_JSON_OUT,
    DEFAULT_SUMMARY_MD_OUT,
    build_analytics_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build SQLite analytics artifacts from canonical trading JSON sources."
    )
    parser.add_argument(
        "--repo-root", default=".", help="Repository root containing data/ and src/."
    )
    parser.add_argument("--db-out", default=str(DEFAULT_DB_OUT), help="SQLite output path.")
    parser.add_argument(
        "--summary-json-out",
        default=str(DEFAULT_SUMMARY_JSON_OUT),
        help="Summary JSON output path.",
    )
    parser.add_argument(
        "--summary-md-out",
        default=str(DEFAULT_SUMMARY_MD_OUT),
        help="Summary markdown output path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_analytics_artifacts(
        Path(args.repo_root),
        db_path=Path(args.db_out),
        summary_json_path=Path(args.summary_json_out),
        summary_md_path=Path(args.summary_md_out),
    )

    latest_account = summary.get("account_daily_pop") or {}
    print(f"SQLite analytics DB written to: {Path(args.db_out)}")
    print(f"Summary JSON written to: {Path(args.summary_json_out)}")
    print(f"Summary markdown written to: {Path(args.summary_md_out)}")
    if latest_account.get("snapshot_date"):
        print(
            "Latest account snapshot: "
            f"{latest_account['snapshot_date']} "
            f"equity={latest_account.get('equity')} "
            f"daily_pnl={latest_account.get('resolved_daily_pnl')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
