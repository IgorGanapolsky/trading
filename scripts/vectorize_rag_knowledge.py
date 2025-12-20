#!/usr/bin/env python3
"""
Phil Town RAG Vectorization Pipeline

Converts Phil Town content (YouTube, Blog, Lessons) into vector embeddings
stored in ChromaDB for semantic search during trading decisions.

Usage:
    python3 scripts/vectorize_rag_knowledge.py --rebuild   # Full rebuild
    python3 scripts/vectorize_rag_knowledge.py --update    # Only new content
    python3 scripts/vectorize_rag_knowledge.py --query "margin of safety"

Weekend automation runs --update mode daily.
"""

import argparse
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
RAG_KNOWLEDGE = Path("rag_knowledge")
VECTOR_DB_PATH = Path("data/vector_db")
VECTORIZE_CACHE = Path("data/vector_db/vectorized_files.json")

# Content sources (Phil Town focused)
CONTENT_SOURCES = {
    "youtube_transcripts": RAG_KNOWLEDGE / "youtube" / "transcripts",
    "youtube_insights": RAG_KNOWLEDGE / "youtube" / "insights",
    "blogs": RAG_KNOWLEDGE / "blogs" / "phil_town",
    "podcasts": RAG_KNOWLEDGE / "podcasts" / "phil_town",
    "lessons_learned": RAG_KNOWLEDGE / "lessons_learned",
    "books": RAG_KNOWLEDGE / "books",
}

# Phil Town key concepts for enhanced retrieval
PHIL_TOWN_CONCEPTS = [
    "margin of safety",
    "moat",
    "big five numbers",
    "rule #1",
    "sticker price",
    "payback time",
    "management quality",
    "meaning",
    "growth rate",
    "PE ratio",
    "roic",
    "equity growth",
    "eps growth",
    "sales growth",
    "cash flow",
    "debt payoff",
    "wonderful company",
    "circle of competence",
    "fear and greed",
    "buy on fear",
]


def get_file_hash(filepath: Path) -> str:
    """Get MD5 hash of file content for change detection."""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def load_vectorize_cache() -> dict:
    """Load cache of already vectorized files."""
    if VECTORIZE_CACHE.exists():
        return json.loads(VECTORIZE_CACHE.read_text())
    return {"files": {}, "last_updated": None}


def save_vectorize_cache(cache: dict):
    """Save vectorize cache."""
    VECTORIZE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache["last_updated"] = datetime.now().isoformat()
    VECTORIZE_CACHE.write_text(json.dumps(cache, indent=2))


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for better retrieval."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > chunk_size // 2:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if len(c) > 50]  # Filter tiny chunks


def extract_phil_town_metadata(text: str, filepath: Path) -> dict:
    """Extract Phil Town specific metadata from content."""
    text_lower = text.lower()

    # Detect which concepts are mentioned
    concepts_found = [c for c in PHIL_TOWN_CONCEPTS if c in text_lower]

    # Detect content type
    content_type = "general"
    if "youtube" in str(filepath):
        content_type = "youtube"
    elif "blog" in str(filepath):
        content_type = "blog"
    elif "podcast" in str(filepath):
        content_type = "podcast"
    elif "lessons" in str(filepath):
        content_type = "lesson_learned"
    elif "book" in str(filepath):
        content_type = "book"

    # Detect if it's about options/puts
    is_options_related = any(term in text_lower for term in [
        "put", "call", "option", "premium", "strike", "expiration",
        "cash-secured", "covered call", "wheel strategy"
    ])

    return {
        "source": filepath.stem,
        "content_type": content_type,
        "concepts": ", ".join(concepts_found) if concepts_found else "none",
        "is_options_related": is_options_related,
        "file_path": str(filepath),
    }


def setup_chroma():
    """Initialize ChromaDB with Phil Town collection."""
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        logger.error("ChromaDB not installed. Run: pip install chromadb")
        return None, None

    VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(VECTOR_DB_PATH),
        settings=Settings(anonymized_telemetry=False)
    )

    # Create or get Phil Town collection
    collection = client.get_or_create_collection(
        name="phil_town_rag",
        metadata={
            "description": "Phil Town Rule #1 Investing knowledge base",
            "created": datetime.now().isoformat(),
            "hnsw:space": "cosine",  # Cosine similarity for text
        }
    )

    return client, collection


def vectorize_file(filepath: Path, collection, cache: dict) -> int:
    """Vectorize a single file and add to collection."""
    file_hash = get_file_hash(filepath)

    # Skip if already vectorized and unchanged
    if str(filepath) in cache["files"]:
        if cache["files"][str(filepath)]["hash"] == file_hash:
            logger.debug(f"Skipping unchanged: {filepath.name}")
            return 0

    # Read content
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {filepath}: {e}")
        return 0

    if len(content) < 100:
        logger.debug(f"Skipping too short: {filepath.name}")
        return 0

    # Extract metadata
    metadata = extract_phil_town_metadata(content, filepath)

    # Chunk the content
    chunks = chunk_text(content)

    if not chunks:
        return 0

    # Add to collection
    ids = [f"{filepath.stem}_{i}" for i in range(len(chunks))]
    metadatas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]

    # Delete old chunks if updating
    try:
        existing = collection.get(where={"source": filepath.stem})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas,
    )

    # Update cache
    cache["files"][str(filepath)] = {
        "hash": file_hash,
        "chunks": len(chunks),
        "vectorized_at": datetime.now().isoformat(),
    }

    logger.info(f"Vectorized: {filepath.name} ({len(chunks)} chunks)")
    return len(chunks)


def vectorize_all(rebuild: bool = False) -> dict:
    """Vectorize all Phil Town content."""
    client, collection = setup_chroma()
    if not collection:
        return {"error": "ChromaDB not available"}

    cache = {} if rebuild else load_vectorize_cache()
    if "files" not in cache:
        cache["files"] = {}

    stats = {"files": 0, "chunks": 0, "skipped": 0, "sources": {}}

    for source_name, source_path in CONTENT_SOURCES.items():
        if not source_path.exists():
            logger.info(f"Creating directory: {source_path}")
            source_path.mkdir(parents=True, exist_ok=True)
            continue

        source_stats = {"files": 0, "chunks": 0}

        # Find all markdown and text files
        for pattern in ["*.md", "*.txt", "*.json"]:
            for filepath in source_path.rglob(pattern):
                chunks = vectorize_file(filepath, collection, cache)
                if chunks > 0:
                    source_stats["files"] += 1
                    source_stats["chunks"] += chunks
                    stats["files"] += 1
                    stats["chunks"] += chunks
                else:
                    stats["skipped"] += 1

        stats["sources"][source_name] = source_stats

    save_vectorize_cache(cache)

    # Get collection stats
    stats["total_documents"] = collection.count()

    return stats


def query_rag(query: str, n_results: int = 5, filter_options: bool = False) -> list[dict]:
    """Query the Phil Town RAG for relevant content."""
    client, collection = setup_chroma()
    if not collection:
        return []

    where_filter = {"is_options_related": True} if filter_options else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    formatted = []
    for i, doc in enumerate(results["documents"][0]):
        concepts_str = results["metadatas"][0][i].get("concepts", "none")
        formatted.append({
            "content": doc[:500] + "..." if len(doc) > 500 else doc,
            "source": results["metadatas"][0][i].get("source", "unknown"),
            "type": results["metadatas"][0][i].get("content_type", "unknown"),
            "concepts": concepts_str.split(", ") if concepts_str != "none" else [],
            "relevance": 1 - results["distances"][0][i],  # Convert distance to similarity
        })

    return formatted


def main():
    parser = argparse.ArgumentParser(description="Phil Town RAG Vectorization")
    parser.add_argument("--rebuild", action="store_true", help="Full rebuild of vector DB")
    parser.add_argument("--update", action="store_true", help="Update with new content only")
    parser.add_argument("--query", type=str, help="Query the RAG")
    parser.add_argument("--options-only", action="store_true", help="Filter to options content")
    parser.add_argument("--stats", action="store_true", help="Show vectorization stats")
    args = parser.parse_args()

    if args.query:
        results = query_rag(args.query, filter_options=args.options_only)
        print(f"\n🔍 Query: {args.query}\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['type']}] {r['source']} (relevance: {r['relevance']:.2f})")
            print(f"   Concepts: {', '.join(r['concepts'][:3]) or 'none'}")
            print(f"   {r['content'][:200]}...")
            print()
        return

    if args.stats:
        cache = load_vectorize_cache()
        client, collection = setup_chroma()
        print("\n📊 RAG Vectorization Stats:")
        print(f"   Last updated: {cache.get('last_updated', 'never')}")
        print(f"   Files vectorized: {len(cache.get('files', {}))}")
        if collection:
            print(f"   Total chunks in DB: {collection.count()}")
        return

    if args.rebuild or args.update:
        print("\n🔄 Vectorizing Phil Town knowledge base...")
        stats = vectorize_all(rebuild=args.rebuild)

        if "error" in stats:
            print(f"❌ Error: {stats['error']}")
            return

        print(f"\n✅ Vectorization complete!")
        print(f"   Files processed: {stats['files']}")
        print(f"   Chunks created: {stats['chunks']}")
        print(f"   Files skipped: {stats['skipped']}")
        print(f"   Total in DB: {stats['total_documents']}")
        print("\n   By source:")
        for source, s in stats["sources"].items():
            if s["files"] > 0:
                print(f"     {source}: {s['files']} files, {s['chunks']} chunks")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
