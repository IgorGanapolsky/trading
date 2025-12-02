#!/usr/bin/env python3
"""RAG health check script.

- Attempts to import the ChromaDB client.
- Reports whether the RAG vector store is available.
- If available, prints collection stats.
- If not, prints a friendly disabled message.
"""

import os
import sys

sys.path.append(os.getcwd())
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        from src.rag.vector_db.chroma_client import get_rag_db

        db = get_rag_db()
        stats = db.get_stats()
        logger.info("✅ RAG vector store is operational.")
        logger.info(f"Total documents: {stats.get('total_documents')}")
        logger.info(f"Unique tickers: {stats.get('unique_tickers')}")
        logger.info(f"Sources: {', '.join(stats.get('sources', []))}")
    except Exception as e:
        logger.warning("⚠️ RAG vector store is not available: %s", e)
        # Provide guidance for missing dependencies
        logger.info(
            "If you wish to enable RAG, ensure 'chromadb' and its dependencies are installed in the current environment."
        )


if __name__ == "__main__":
    main()
