#!/usr/bin/env python3
"""CLI entrypoint to refresh RL filter weights from telemetry."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.agents.rl_agent import RLFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update RL filter weights from telemetry.")
    parser.add_argument(
        "--audit-log",
        default="data/audit_trail/hybrid_funnel_runs.jsonl",
        help="Path to telemetry JSONL file.",
    )
    parser.add_argument(
        "--model-out",
        default="models/ml/rl_filter_policy.zip",
        help="Path to save the PPO policy checkpoint.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all computations but skip writing weights/model artifacts.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print summary JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rl_filter = RLFilter()
    summary = rl_filter.update_from_telemetry(
        audit_path=args.audit_log,
        model_path=args.model_out,
        dry_run=args.dry_run,
    )

    dump = json.dumps(summary, indent=2 if args.pretty else None)
    print(dump)


if __name__ == "__main__":
    main()
