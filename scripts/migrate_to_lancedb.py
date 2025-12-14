#!/usr/bin/env python3
"""
Migration Script: ChromaDB/JSON → LanceDB

Migrates vectorized documents from ChromaDB and/or in-memory JSON store to LanceDB.
Uses FastEmbed (BAAI/bge-small-en-v1.5) for re-embedding with proper deduplication.

Usage:
    python scripts/migrate_to_lancedb.py --source chromadb  # Migrate from ChromaDB only
    python scripts/migrate_to_lancedb.py --source json      # Migrate from JSON only
    python scripts/migrate_to_lancedb.py --source all       # Migrate from both (dedupe)
    python scripts/migrate_to_lancedb.py --dry-run          # Preview without writing
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Try to import dependencies
try:
    import lancedb
    import pyarrow as pa
    from fastembed import TextEmbedding
    from tqdm import tqdm
except ImportError as e:
    logger.error(f"Missing required dependency: {e}")
    logger.error("Install with: pip install lancedb fastembed pyarrow tqdm")
    sys.exit(1)


class LanceDBMigrator:
    """Migrates RAG data from ChromaDB/JSON to LanceDB."""

    def __init__(
        self,
        chromadb_path: str = "data/rag/chroma_db",
        json_path: str = "data/rag/in_memory_store.json",
        lancedb_path: str = "data/rag/lance_db",
        model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        self.chromadb_path = chromadb_path
        self.json_path = json_path
        self.lancedb_path = lancedb_path
        self.model_name = model_name

        # Initialize FastEmbed
        logger.info(f"Loading embedding model: {model_name}")
        self.embedder = TextEmbedding(model_name=model_name)
        logger.info(f"Embedding dimension: {self.embedder.embed('test').shape[-1]}")

        # Track stats
        self.stats = {
            "chromadb_docs": 0,
            "json_docs": 0,
            "total_before_dedup": 0,
            "duplicates_removed": 0,
            "final_docs": 0,
            "errors": 0,
        }

    def _hash_document(self, doc: str) -> str:
        """Create hash of document content for deduplication."""
        return hashlib.sha256(doc.encode("utf-8")).hexdigest()[:16]

    def read_from_chromadb(self) -> list[dict[str, Any]]:
        """Read all documents from ChromaDB."""
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
            return []

        if not os.path.exists(self.chromadb_path):
            logger.warning(f"ChromaDB path not found: {self.chromadb_path}")
            return []

        try:
            logger.info(f"Reading from ChromaDB: {self.chromadb_path}")
            client = chromadb.PersistentClient(path=self.chromadb_path)
            collection = client.get_or_create_collection(
                name="market_news", metadata={"hnsw:space": "cosine"}
            )

            count = collection.count()
            logger.info(f"Found {count} documents in ChromaDB")

            if count == 0:
                return []

            # Get all documents
            results = collection.get(limit=count)

            docs = []
            for i in range(len(results["documents"])):
                doc_data = {
                    "id": results["ids"][i],
                    "document": results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    "source": "chromadb",
                }
                docs.append(doc_data)

            self.stats["chromadb_docs"] = len(docs)
            logger.info(f"Successfully read {len(docs)} documents from ChromaDB")
            return docs

        except Exception as e:
            logger.error(f"Error reading from ChromaDB: {e}")
            self.stats["errors"] += 1
            return []

    def read_from_json(self) -> list[dict[str, Any]]:
        """Read all documents from JSON store."""
        if not os.path.exists(self.json_path):
            logger.warning(f"JSON path not found: {self.json_path}")
            return []

        try:
            logger.info(f"Reading from JSON: {self.json_path}")
            with open(self.json_path) as f:
                data = json.load(f)

            documents = data.get("documents", [])
            metadatas = data.get("metadatas", [])
            ids = data.get("ids", [])

            logger.info(f"Found {len(documents)} documents in JSON store")

            docs = []
            for i in range(len(documents)):
                doc_data = {
                    "id": ids[i] if i < len(ids) else f"json_{i}",
                    "document": documents[i],
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "source": "json",
                }
                docs.append(doc_data)

            self.stats["json_docs"] = len(docs)
            logger.info(f"Successfully read {len(docs)} documents from JSON")
            return docs

        except Exception as e:
            logger.error(f"Error reading from JSON: {e}")
            self.stats["errors"] += 1
            return []

    def deduplicate_documents(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate documents based on content hash."""
        logger.info("Deduplicating documents...")
        self.stats["total_before_dedup"] = len(docs)

        seen_hashes = {}
        deduplicated = []

        for doc in tqdm(docs, desc="Deduplicating"):
            doc_hash = self._hash_document(doc["document"])

            if doc_hash in seen_hashes:
                self.stats["duplicates_removed"] += 1
                # Keep the one from ChromaDB if both exist
                if doc["source"] == "chromadb":
                    # Replace JSON version with ChromaDB version
                    existing_idx = seen_hashes[doc_hash]
                    if deduplicated[existing_idx]["source"] == "json":
                        deduplicated[existing_idx] = doc
            else:
                seen_hashes[doc_hash] = len(deduplicated)
                deduplicated.append(doc)

        self.stats["final_docs"] = len(deduplicated)
        logger.info(
            f"Removed {self.stats['duplicates_removed']} duplicates, "
            f"{len(deduplicated)} unique documents remaining"
        )

        return deduplicated

    def embed_documents(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate embeddings for all documents using FastEmbed."""
        logger.info(f"Generating embeddings for {len(docs)} documents...")

        # Extract document texts
        texts = [doc["document"] for doc in docs]

        # Generate embeddings in batches
        embeddings = []
        batch_size = 256

        with tqdm(total=len(texts), desc="Embedding") as pbar:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                try:
                    batch_embeddings = list(self.embedder.embed(batch))
                    embeddings.extend(batch_embeddings)
                    pbar.update(len(batch))
                except Exception as e:
                    logger.error(f"Error embedding batch {i}: {e}")
                    # Add zero vectors for failed embeddings
                    for _ in batch:
                        embeddings.append([0.0] * 384)  # bge-small-en-v1.5 is 384-dim
                    self.stats["errors"] += 1
                    pbar.update(len(batch))

        # Add embeddings to documents
        for doc, embedding in zip(docs, embeddings, strict=False):
            doc["vector"] = embedding.tolist() if hasattr(embedding, "tolist") else embedding

        logger.info(f"Successfully generated {len(embeddings)} embeddings")
        return docs

    def create_lancedb_schema(self) -> pa.Schema:
        """Create PyArrow schema for LanceDB table."""
        return pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("document", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)),  # bge-small-en-v1.5
                # Metadata fields
                pa.field("ticker", pa.string()),
                pa.field("source", pa.string()),
                pa.field("date", pa.string()),
                pa.field("url", pa.string()),
                pa.field("sentiment", pa.string()),
                # Migration metadata
                pa.field("migrated_from", pa.string()),
                pa.field("migrated_at", pa.string()),
            ]
        )

    def write_to_lancedb(self, docs: list[dict[str, Any]]) -> bool:
        """Write documents to LanceDB."""
        try:
            logger.info(f"Writing {len(docs)} documents to LanceDB: {self.lancedb_path}")

            # Create LanceDB directory if it doesn't exist
            os.makedirs(self.lancedb_path, exist_ok=True)

            # Connect to LanceDB
            db = lancedb.connect(self.lancedb_path)

            # Prepare data for LanceDB
            migration_timestamp = datetime.now().isoformat()
            table_data = []

            for doc in tqdm(docs, desc="Preparing LanceDB records"):
                metadata = doc.get("metadata", {})

                record = {
                    "id": doc["id"],
                    "document": doc["document"],
                    "vector": doc["vector"],
                    # Metadata
                    "ticker": metadata.get("ticker", ""),
                    "source": metadata.get("source", ""),
                    "date": metadata.get("date", ""),
                    "url": metadata.get("url", ""),
                    "sentiment": metadata.get("sentiment", ""),
                    # Migration metadata
                    "migrated_from": doc["source"],
                    "migrated_at": migration_timestamp,
                }
                table_data.append(record)

            # Create or overwrite table
            schema = self.create_lancedb_schema()

            # Drop table if it exists
            try:
                db.drop_table("market_news")
                logger.info("Dropped existing LanceDB table")
            except Exception:
                pass  # Table doesn't exist, that's fine

            # Create new table
            table = db.create_table("market_news", data=table_data, schema=schema)

            # Create vector index for fast similarity search
            logger.info("Creating vector index...")
            table.create_index(metric="cosine", num_partitions=8, num_sub_vectors=16)

            logger.info(f"✅ Successfully wrote {len(table_data)} documents to LanceDB")
            return True

        except Exception as e:
            logger.error(f"Error writing to LanceDB: {e}")
            self.stats["errors"] += 1
            return False

    def print_stats(self):
        """Print migration statistics."""
        print("\n" + "=" * 60)
        print("MIGRATION STATISTICS")
        print("=" * 60)
        print(f"ChromaDB documents read:      {self.stats['chromadb_docs']:,}")
        print(f"JSON documents read:          {self.stats['json_docs']:,}")
        print(f"Total before deduplication:   {self.stats['total_before_dedup']:,}")
        print(f"Duplicates removed:           {self.stats['duplicates_removed']:,}")
        print(f"Final unique documents:       {self.stats['final_docs']:,}")
        print(f"Errors encountered:           {self.stats['errors']}")
        print("=" * 60)

        if self.stats["final_docs"] > 0:
            dedup_rate = self.stats["duplicates_removed"] / self.stats["total_before_dedup"] * 100
            print(f"Deduplication rate:           {dedup_rate:.1f}%")
            print("=" * 60)

    def migrate(self, source: str = "all", dry_run: bool = False):
        """
        Execute migration from ChromaDB/JSON to LanceDB.

        Args:
            source: Source to migrate from ('chromadb', 'json', or 'all')
            dry_run: If True, preview without writing to LanceDB
        """
        docs = []

        # Read from sources
        if source in ["chromadb", "all"]:
            chromadb_docs = self.read_from_chromadb()
            docs.extend(chromadb_docs)

        if source in ["json", "all"]:
            json_docs = self.read_from_json()
            docs.extend(json_docs)

        if not docs:
            logger.error("No documents found to migrate!")
            return False

        # Deduplicate
        docs = self.deduplicate_documents(docs)

        # Generate embeddings
        docs = self.embed_documents(docs)

        # Write to LanceDB
        if dry_run:
            logger.info("DRY RUN - skipping write to LanceDB")
            logger.info(f"Would have written {len(docs)} documents")
        else:
            success = self.write_to_lancedb(docs)
            if not success:
                logger.error("Migration failed!")
                self.print_stats()
                return False

        # Print statistics
        self.print_stats()

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate RAG data from ChromaDB/JSON to LanceDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate from ChromaDB only
  python scripts/migrate_to_lancedb.py --source chromadb

  # Migrate from JSON only
  python scripts/migrate_to_lancedb.py --source json

  # Migrate from both (with deduplication)
  python scripts/migrate_to_lancedb.py --source all

  # Dry run (preview without writing)
  python scripts/migrate_to_lancedb.py --dry-run
        """,
    )

    parser.add_argument(
        "--source",
        choices=["chromadb", "json", "all"],
        default="all",
        help="Source to migrate from (default: all)",
    )

    parser.add_argument(
        "--chromadb-path",
        default="data/rag/chroma_db",
        help="Path to ChromaDB (default: data/rag/chroma_db)",
    )

    parser.add_argument(
        "--json-path",
        default="data/rag/in_memory_store.json",
        help="Path to JSON store (default: data/rag/in_memory_store.json)",
    )

    parser.add_argument(
        "--lancedb-path",
        default="data/rag/lance_db",
        help="Path to LanceDB (default: data/rag/lance_db)",
    )

    parser.add_argument(
        "--model",
        default="BAAI/bge-small-en-v1.5",
        help="FastEmbed model name (default: BAAI/bge-small-en-v1.5)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing to LanceDB",
    )

    args = parser.parse_args()

    # Create migrator
    migrator = LanceDBMigrator(
        chromadb_path=args.chromadb_path,
        json_path=args.json_path,
        lancedb_path=args.lancedb_path,
        model_name=args.model,
    )

    # Run migration
    success = migrator.migrate(source=args.source, dry_run=args.dry_run)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
