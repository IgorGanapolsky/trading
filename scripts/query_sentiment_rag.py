#!/usr/bin/env python3
"""
Quick utility for querying the sentiment RAG store from the terminal.

Examples:
    python scripts/query_sentiment_rag.py --query "NVDA earnings outlook"
    python scripts/query_sentiment_rag.py --ticker NVDA --limit 5
"""

import argparse
import logging
import sys

sys.path.append(".")

from src.rag.sentiment_store import SentimentRAGStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the sentiment RAG store.")
    parser.add_argument(
        "--query",
        help="Semantic query to run (defaults to ticker sentiment summary).",
    )
    parser.add_argument(
        "--ticker",
        help="Ticker symbol to filter on (e.g., SPY, NVDA).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of results to display (default: 5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    store = SentimentRAGStore()

    if args.query:
        results = store.query(query=args.query, ticker=args.ticker, top_k=args.limit)
    elif args.ticker:
        results = store.get_ticker_history(ticker=args.ticker, limit=args.limit)
    else:
        logging.error("Provide at least --query or --ticker.")
        sys.exit(1)

    if not results:
        logging.info("No sentiment entries found for the given request.")
        return

    for idx, entry in enumerate(results, start=1):
        metadata = entry.get("metadata", {})
        print("=" * 80)
        print(f"Result #{idx}")
        print(f"ID: {entry.get('id')}")
        print(f"Score: {entry.get('score'):.3f}")
        print(
            f"Date: {metadata.get('snapshot_date')} | "
            f"Ticker: {metadata.get('ticker')} | "
            f"Sentiment Score: {metadata.get('sentiment_score')} | "
            f"Confidence: {metadata.get('confidence')} | "
            f"Regime: {metadata.get('market_regime')}"
        )
        print("Sources:", metadata.get("source_list"))
        print("-" * 80)
        print(entry.get("document", "").strip())
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
