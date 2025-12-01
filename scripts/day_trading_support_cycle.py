#!/usr/bin/env python3
"""Run the agentic day-trading support orchestrator end-to-end."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from src.day_trading_support import DayTradeSupportOrchestrator
from src.day_trading_support.config_loader import load_resource_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate coaching, reading, and newsletter prep artifacts."
    )
    parser.add_argument(
        "--focus",
        dest="focus_tags",
        action="append",
        default=None,
        help="Optional focus tags (e.g., psychology, execution). Repeatable.",
    )
    parser.add_argument(
        "--study-minutes",
        type=int,
        default=60,
        help="Target number of study minutes to allocate.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Override path to day_trading_resources.yaml",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print raw JSON payload to stdout in addition to writing files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_resource_config(args.config)
    orchestrator = DayTradeSupportOrchestrator(config=config)
    plan = orchestrator.run(
        focus_tags=args.focus_tags,
        study_minutes=args.study_minutes,
    )
    if args.print_json:
        print(json.dumps(plan.to_dict(), indent=2))
    print(orchestrator.summarize(plan))


if __name__ == "__main__":
    main()
