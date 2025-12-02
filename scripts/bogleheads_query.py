#!/usr/bin/env python3
"""
Query latest Bogleheads snapshots from the Sentiment RAG store.

Usage:
  python scripts/bogleheads_query.py --limit 3 --format md
"""

import argparse

from src.rag.sentiment_store import SentimentRAGStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Bogleheads snapshots")
    parser.add_argument("--limit", type=int, default=3, help="Number of entries")
    parser.add_argument(
        "--format",
        choices=["json", "md"],
        default="md",
        help="Output format",
    )
    args = parser.parse_args()

    store = SentimentRAGStore()
    rows = store.get_ticker_history("MARKET", limit=args.limit)

    if args.format == "json":
        import json

        print(json.dumps(rows, indent=2, default=str))
        return 0

    # Markdown
    print("## Bogleheads Snapshots (Latest)")
    for row in rows:
        meta = row.get("metadata", {})
        date = meta.get("snapshot_date", "n/a")
        regime = meta.get("market_regime", "unknown")
        conf = meta.get("confidence", "n/a")
        print(f"- Date: `{date}` | Regime: `{regime}` | Confidence: `{conf}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
