#!/usr/bin/env python3
"""
Test script for GraphRAG Lite.
"""

import logging
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.rag.knowledge_graph import get_knowledge_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("🚀 Testing GraphRAG Lite...")

    kg = get_knowledge_graph()

    # 1. Add some dummy documents
    logger.info("Adding documents...")
    kg.add_document("NVDA and AMD are competing in the AI chip market.", source_ticker="NVDA")
    kg.add_document("TSLA uses NVDA chips for self-driving.", source_ticker="TSLA")
    kg.add_document("AAPL and MSFT are tech giants.", source_ticker="AAPL")
    kg.add_document("AMD is gaining market share from INTC.", source_ticker="AMD")

    kg.save_graph()

    # 2. Query relationships
    tickers = ["NVDA", "AMD", "TSLA", "AAPL"]

    for t in tickers:
        related = kg.get_related_tickers(t)
        logger.info(f"Related to {t}: {related}")

    logger.info("✅ GraphRAG Test Complete!")


if __name__ == "__main__":
    main()
