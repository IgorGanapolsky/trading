#!/usr/bin/env python3
"""
Ingest cached sentiment snapshots into the SQLite-backed RAG store.

Usage:
    python scripts/ingest_sentiment_rag.py --days 60 --rebuild
"""

import argparse
import logging
import sys

sys.path.append(".")

from src.rag.sentiment_store import SentimentRAGStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or refresh the sentiment RAG vector store.")
    parser.add_argument(
        "--days",
        type=int,
        default=60,
        help="Number of days of sentiment snapshots to ingest (default: 60).",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Reset the sentiment store before ingesting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    store = SentimentRAGStore()

    if args.rebuild:
        logging.info("Resetting sentiment store")
        store.reset()

    count = store.ingest_from_cache(days=args.days)
    logging.info("Ingestion complete. %d documents stored.", count)


if __name__ == "__main__":
    main()
