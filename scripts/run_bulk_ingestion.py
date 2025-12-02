#!/usr/bin/env python3
"""
Bulk Ingestion Script for RAG System.

Runs the full RAG ingestion pipeline for a set of watchlist tickers.
Populates the persistent in-memory vector store.
"""

import logging
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.rag.ingestion_pipeline import get_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("🚀 Starting Bulk RAG Ingestion...")

    pipeline = get_pipeline()

    # 1. Ingest General Market News (Reddit, Bogleheads, etc.)
    logger.info("\n🌍 Ingesting General Market News...")
    pipeline.ingest_market_news(days_back=2)

    # 2. Ingest Ticker-Specific News
    # Using a representative list of tickers
    watchlist = ["NVDA", "AAPL", "TSLA", "AMD", "SPY", "QQQ", "MSFT", "GOOGL", "AMZN", "META"]
    logger.info(f"\n📈 Ingesting News for Watchlist: {watchlist}")

    pipeline.ingest_watchlist_news(watchlist, days_back=3)

    logger.info("\n✅ Bulk Ingestion Complete!")


if __name__ == "__main__":
    main()
