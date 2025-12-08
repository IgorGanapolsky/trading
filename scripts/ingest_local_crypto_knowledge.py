#!/usr/bin/env python3
"""
Ingest Local Crypto Knowledge into RAG

Loads crypto trading knowledge from local JSON files into the RAG store.
No network dependencies - works offline.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
RAG_STORE_PATH = PROJECT_ROOT / "data" / "rag" / "in_memory_store.json"
CRYPTO_KNOWLEDGE_FILES = [
    PROJECT_ROOT / "rag_knowledge" / "chunks" / "crypto_ai_2025.json",
    PROJECT_ROOT / "rag_knowledge" / "chunks" / "crypto_trading_mastery_2025.json",
]


def load_existing_store() -> dict:
    """Load existing RAG store or create new one."""
    if RAG_STORE_PATH.exists():
        try:
            with open(RAG_STORE_PATH) as f:
                store = json.load(f)
                logger.info(f"Loaded existing store with {len(store.get('documents', []))} documents")
                return store
        except Exception as e:
            logger.warning(f"Failed to load existing store: {e}")

    return {"documents": [], "metadatas": [], "ids": []}


def ingest_crypto_chunks(store: dict, filepath: Path) -> int:
    """Ingest chunks from a crypto knowledge file."""
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return 0

    try:
        with open(filepath) as f:
            chunks = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return 0

    existing_docs = set(store.get("documents", []))
    added = 0

    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "")

        # Skip if already exists
        if content in existing_docs:
            continue

        # Create document entry
        doc_id = f"crypto_{filepath.stem}_{i}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        metadata = {
            "source": chunk.get("source_name", "Unknown"),
            "author": chunk.get("author", "Unknown"),
            "section": chunk.get("chapter_or_section", ""),
            "content_type": chunk.get("content_type", "text"),
            "topics": ",".join(chunk.get("topics", [])),
            "edge_category": chunk.get("edge_category", "crypto"),
            "ingested_at": datetime.now().isoformat(),
        }

        store["documents"].append(content)
        store["metadatas"].append(metadata)
        store["ids"].append(doc_id)
        added += 1

    return added


def save_store(store: dict) -> bool:
    """Save the RAG store."""
    try:
        RAG_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RAG_STORE_PATH, "w") as f:
            json.dump(store, f, indent=2, default=str)
        logger.info(f"Saved store with {len(store['documents'])} total documents")
        return True
    except Exception as e:
        logger.error(f"Failed to save store: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("CRYPTO KNOWLEDGE RAG INGESTION")
    logger.info("=" * 60)

    # Load existing store
    store = load_existing_store()

    total_added = 0

    # Ingest each crypto knowledge file
    for filepath in CRYPTO_KNOWLEDGE_FILES:
        logger.info(f"Processing: {filepath.name}")
        added = ingest_crypto_chunks(store, filepath)
        logger.info(f"  Added {added} new chunks")
        total_added += added

    # Save updated store
    if total_added > 0:
        if save_store(store):
            logger.info(f"SUCCESS: Added {total_added} crypto knowledge chunks to RAG")
        else:
            logger.error("FAILED to save RAG store")
            return 1
    else:
        logger.info("No new chunks to add (all already present)")

    # Verify crypto content
    crypto_docs = [d for d in store["documents"] if "crypto" in d.lower() or "btc" in d.lower() or "bitcoin" in d.lower()]
    logger.info(f"Total crypto-related documents in RAG: {len(crypto_docs)}")

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
