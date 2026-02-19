#!/usr/bin/env python3
"""CLI wrapper for distributed Thompson feedback aggregation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.learning.distributed_feedback import aggregate_feedback


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate feedback across workers via all_reduce.")
    parser.add_argument("--event-key", required=True, help="Stable dedupe key for the feedback event")
    parser.add_argument(
        "--feedback",
        required=True,
        choices=["positive", "negative"],
        help="Feedback polarity",
    )
    parser.add_argument("--context", default="", help="Context used for feature updates")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root path (defaults to current directory)",
    )
    args = parser.parse_args()

    outcome = aggregate_feedback(
        project_root=Path(args.project_root).resolve(),
        event_key=args.event_key,
        feedback_type=args.feedback,
        context=args.context,
    )
    print(json.dumps(outcome, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

