#!/usr/bin/env python3
r"""Trading-native feedback capture (no ThumbGate).

capture thumbs-down -> normalize/quality-gate -> SQLite FTS5 (+ markdown lesson).

Usage:
    python scripts/capture_trading_feedback.py --signal negative \
      --context "spy put credit entry" \
      --what-went-wrong "Opened 10-lot violating 1-lot rule" \
      --what-to-change "Enforce MAX_LOT_SIZE=1 in trade gateway before submit"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.retrieve_for_trade import capture_and_store_feedback  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture trading feedback into FTS5 lessons")
    parser.add_argument("--signal", required=True, choices=["negative", "positive", "down", "up"])
    parser.add_argument("--context", default="")
    parser.add_argument("--what-went-wrong", default="")
    parser.add_argument("--what-to-change", default="")
    parser.add_argument("--what-worked", default="")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--no-markdown", action="store_true")
    args = parser.parse_args()
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    result = capture_and_store_feedback(
        signal=args.signal,
        context=args.context,
        what_went_wrong=args.what_went_wrong,
        what_to_change=args.what_to_change,
        what_worked=args.what_worked,
        tags=tags or None,
        also_write_markdown=not args.no_markdown,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
