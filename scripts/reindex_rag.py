#!/usr/bin/env python3
"""
RAG Reindexing Script - 2026 Best Practices

This script vectorizes all lessons learned and RAG knowledge using:
- LanceDB: Embedded vector database (no external server needed)
- Sentence Transformers: BAAI/bge-small-en-v1.5 (high accuracy, fast)
- Semantic Chunking: Preserves meaning boundaries

Based on 2026 research:
- https://lancedb.com/docs/integrations/embedding/sentence-transformers/
- https://weaviate.io/blog/chunking-strategies-for-rag
- https://medium.com/@adnanmasood/chunking-strategies-for-rag

Usage:
    python3 scripts/reindex_rag.py
    python3 scripts/reindex_rag.py --force  # Rebuild from scratch
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
RAG_KNOWLEDGE_DIR = Path(__file__).parent.parent / "rag_knowledge"
LANCEDB_PATH = Path(__file__).parent.parent / ".claude" / "memory" / "lancedb"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # Best balance of speed/accuracy per 2026 research
CHUNK_SIZE = 500  # ~500 chars per chunk (semantic boundaries preferred)
CHUNK_OVERLAP = 50  # Overlap to preserve context


def get_file_hash(content: str) -> str:
    """Generate hash of content for change detection."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def semantic_chunk(
    text: str, max_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """
    Semantic chunking - split on meaningful boundaries.

    2026 Best Practice: Split on paragraph/sentence boundaries, not arbitrary positions.
    Reference: https://weaviate.io/blog/chunking-strategies-for-rag
    """
    # Split on paragraph boundaries first
    paragraphs = re.split(r"\n\n+", text)

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If paragraph fits, add it
        if len(current_chunk) + len(para) + 2 <= max_size:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
        else:
            # Save current chunk if non-empty
            if current_chunk:
                chunks.append(current_chunk.strip())

            # If paragraph itself is too large, split on sentences
            if len(para) > max_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= max_size:
                        current_chunk = f"{current_chunk} {sent}" if current_chunk else sent
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sent
            else:
                current_chunk = para

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def extract_metadata(filepath: Path, content: str) -> dict:
    """Extract metadata from lesson file."""
    metadata = {
        "source": str(filepath.relative_to(RAG_KNOWLEDGE_DIR)),
        "filename": filepath.name,
        "category": filepath.parent.name,
        "indexed_at": datetime.now().isoformat(),
    }

    # Extract date from filename (e.g., ll_319_..._jan30.md)
    date_match = re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{1,2})",
        filepath.name.lower(),
    )
    if date_match:
        metadata["date_hint"] = f"{date_match.group(1)}{date_match.group(2)}"

    # Extract severity if present
    if "CRITICAL" in content.upper():
        metadata["severity"] = "critical"
    elif "HIGH" in content.upper():
        metadata["severity"] = "high"
    elif "WARNING" in content.upper():
        metadata["severity"] = "warning"

    # Extract lesson ID (LL-XXX or ll_XXX)
    id_match = re.search(r"[Ll][Ll][-_]?(\d+)", filepath.name)
    if id_match:
        metadata["lesson_id"] = f"LL-{id_match.group(1)}"

    return metadata


def index_documents(force: bool = False) -> dict:
    """
    Index all RAG knowledge documents into LanceDB.

    Returns:
        dict with indexing statistics
    """
    try:
        import lancedb
        from lancedb.embeddings import get_registry
        from lancedb.pydantic import LanceModel, Vector
    except ImportError:
        logger.error("LanceDB not installed. Run: pip install lancedb sentence-transformers")
        return {
            "files_processed": 0,
            "chunks_created": 0,
            "errors": ["LanceDB not installed"],
        }

    # Create LanceDB directory
    LANCEDB_PATH.mkdir(parents=True, exist_ok=True)

    # Initialize embedding model
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = (
        get_registry()
        .get("sentence-transformers")
        .create(
            name=EMBEDDING_MODEL,
            device="cpu",  # Use CPU for compatibility
        )
    )

    # Define schema
    class RAGDocument(LanceModel):
        text: str = model.SourceField()
        vector: Vector(model.ndims()) = model.VectorField()
        source: str
        filename: str
        category: str
        chunk_index: int
        content_hash: str
        indexed_at: str
        severity: Optional[str] = None
        lesson_id: Optional[str] = None
        date_hint: Optional[str] = None

    # Connect to database
    db = lancedb.connect(str(LANCEDB_PATH))

    # Rebuild table to avoid duplicate accumulation across repeated runs.
    # This keeps retrieval quality stable without requiring manual --force.
    if "rag_knowledge" in db.table_names():
        if force:
            logger.info("Force rebuild: dropping existing table")
        else:
            logger.info(
                "Existing rag_knowledge table detected; rebuilding to prevent duplicate chunks"
            )
        db.drop_table("rag_knowledge")

    # Collect all documents
    documents = []
    stats = {
        "files_processed": 0,
        "chunks_created": 0,
        "errors": [],
    }

    # Find all markdown files
    md_files = list(RAG_KNOWLEDGE_DIR.rglob("*.md"))
    logger.info(f"Found {len(md_files)} markdown files to index")

    for filepath in md_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            if not content.strip():
                continue

            metadata = extract_metadata(filepath, content)
            content_hash = get_file_hash(content)

            # Semantic chunking
            chunks = semantic_chunk(content)

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                doc = {
                    "text": chunk,
                    "source": metadata["source"],
                    "filename": metadata["filename"],
                    "category": metadata["category"],
                    "chunk_index": i,
                    "content_hash": content_hash,
                    "indexed_at": metadata["indexed_at"],
                    "severity": metadata.get("severity"),
                    "lesson_id": metadata.get("lesson_id"),
                    "date_hint": metadata.get("date_hint"),
                }
                documents.append(doc)
                stats["chunks_created"] += 1

            stats["files_processed"] += 1

        except Exception as e:
            stats["errors"].append(f"{filepath.name}: {e}")
            logger.error(f"Error processing {filepath}: {e}")

    # Create or update table
    if documents:
        logger.info(f"Creating embeddings for {len(documents)} chunks...")

        db.create_table("rag_knowledge", data=documents, schema=RAGDocument)

        logger.info(f"Indexed {stats['files_processed']} files, {stats['chunks_created']} chunks")
    else:
        logger.warning("No documents found to index")

    return stats


def search_rag(query: str, limit: int = 5) -> list[dict]:
    """
    Search the RAG knowledge base.

    Args:
        query: Search query
        limit: Max results to return

    Returns:
        List of relevant documents with scores
    """
    try:
        import lancedb
    except ImportError:
        logger.error("LanceDB not installed. Run: pip install lancedb sentence-transformers")
        return []

    if not LANCEDB_PATH.exists():
        logger.error("RAG index not found. Run: python3 scripts/reindex_rag.py")
        return []

    db = lancedb.connect(str(LANCEDB_PATH))

    if "rag_knowledge" not in db.table_names():
        logger.error("RAG table not found. Run: python3 scripts/reindex_rag.py")
        return []

    table = db.open_table("rag_knowledge")

    # Search with the same embedding model
    results = table.search(query).limit(limit).to_list()

    return results


def main():
    parser = argparse.ArgumentParser(description="Reindex RAG knowledge base")
    parser.add_argument("--force", action="store_true", help="Force complete rebuild")
    parser.add_argument("--search", type=str, help="Test search query")
    args = parser.parse_args()

    if args.search:
        # Search mode
        logger.info(f"Searching for: {args.search}")
        results = search_rag(args.search, limit=5)

        print("\n" + "=" * 60)
        print(f"Search Results for: {args.search}")
        print("=" * 60)

        for i, result in enumerate(results, 1):
            print(
                f"\n[{i}] {result.get('filename', 'unknown')} (chunk {result.get('chunk_index', 0)})"
            )
            if result.get("lesson_id"):
                print(f"    Lesson: {result['lesson_id']}")
            if result.get("severity"):
                print(f"    Severity: {result['severity']}")
            print("    ---")
            # Show first 200 chars of content
            text = result.get("text", "")[:200]
            print(f"    {text}...")

        return

    # Index mode
    print("=" * 60)
    print("RAG Knowledge Base Reindexing")
    print("=" * 60)
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Database: {LANCEDB_PATH}")
    print(f"Knowledge dir: {RAG_KNOWLEDGE_DIR}")
    print("=" * 60)

    stats = index_documents(force=args.force)

    print("\n" + "=" * 60)
    print("Indexing Complete")
    print("=" * 60)
    print(f"Files processed: {stats['files_processed']}")
    print(f"Chunks created: {stats['chunks_created']}")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for err in stats["errors"][:5]:
            print(f"  - {err}")

    # Save stats
    stats_file = LANCEDB_PATH / "index_stats.json"
    stats_file.parent.mkdir(parents=True, exist_ok=True)
    stats["last_indexed"] = datetime.now().isoformat()
    stats_file.write_text(json.dumps(stats, indent=2))
    print(f"\nStats saved to: {stats_file}")


if __name__ == "__main__":
    main()
