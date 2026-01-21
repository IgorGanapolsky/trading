#!/usr/bin/env python3
"""
Phil Town RAG Knowledge Indexing Pipeline

Indexes Phil Town content (YouTube, Blog, Lessons) for keyword-based search.
For cloud-based semantic search, use Vertex AI RAG via CI workflows.

Usage:
    python3 scripts/vectorize_rag_knowledge.py --rebuild   # Full rebuild of local index
    python3 scripts/vectorize_rag_knowledge.py --update    # Only new content
    python3 scripts/vectorize_rag_knowledge.py --query "margin of safety"

Updated: Jan 7, 2026 - Removed ChromaDB dependency (CEO directive)
"""

import argparse
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
RAG_KNOWLEDGE = Path("rag_knowledge")
INDEX_CACHE = Path("data/vector_db/vectorized_files.json")

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


def load_index_cache() -> dict:
    """Load cache of already indexed files."""
    if INDEX_CACHE.exists():
        return json.loads(INDEX_CACHE.read_text())
    return {"files": {}, "last_updated": None}


def save_index_cache(cache: dict):
    """Save index cache."""
    INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache["last_updated"] = datetime.now().isoformat()
    INDEX_CACHE.write_text(json.dumps(cache, indent=2))


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
    is_options_related = any(
        term in text_lower
        for term in [
            "put",
            "call",
            "option",
            "premium",
            "strike",
            "expiration",
            "cash-secured",
            "covered call",
            "wheel strategy",
        ]
    )

    return {
        "source": filepath.stem,
        "content_type": content_type,
        "concepts": concepts_found,
        "is_options_related": is_options_related,
        "file_path": str(filepath),
    }


def index_file(filepath: Path, cache: dict) -> bool:
    """Index a single file and add to local cache."""
    file_hash = get_file_hash(filepath)

    # Skip if already indexed and unchanged
    if str(filepath) in cache["files"]:
        if cache["files"][str(filepath)]["hash"] == file_hash:
            logger.debug(f"Skipping unchanged: {filepath.name}")
            return False

    # Read content
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {filepath}: {e}")
        return False

    if len(content) < 100:
        logger.debug(f"Skipping too short: {filepath.name}")
        return False

    # Extract metadata
    metadata = extract_phil_town_metadata(content, filepath)

    # Update cache
    cache["files"][str(filepath)] = {
        "hash": file_hash,
        "metadata": metadata,
        "indexed_at": datetime.now().isoformat(),
        "size": len(content),
    }

    logger.info(f"Indexed: {filepath.name} (type: {metadata['content_type']})")
    return True


def index_all(rebuild: bool = False) -> dict:
    """Index all Phil Town content."""
    cache = {} if rebuild else load_index_cache()
    if "files" not in cache:
        cache["files"] = {}

    stats = {"files": 0, "skipped": 0, "sources": {}}

    for source_name, source_path in CONTENT_SOURCES.items():
        if not source_path.exists():
            logger.info(f"Creating directory: {source_path}")
            source_path.mkdir(parents=True, exist_ok=True)
            continue

        source_stats = {"files": 0}

        # Find all markdown and text files
        for pattern in ["*.md", "*.txt", "*.json"]:
            for filepath in source_path.rglob(pattern):
                if index_file(filepath, cache):
                    source_stats["files"] += 1
                    stats["files"] += 1
                else:
                    stats["skipped"] += 1

        stats["sources"][source_name] = source_stats

    save_index_cache(cache)

    # Get total indexed files
    stats["total_indexed"] = len(cache.get("files", {}))

    return stats


def query_rag(query: str, n_results: int = 5, filter_options: bool = False) -> list[dict]:
    """Query the Phil Town knowledge base using keyword search."""
    try:
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        results = search.search(query, top_k=n_results)

        formatted = []
        for lesson, score in results:
            # Filter options content if requested
            if filter_options:
                content_lower = lesson.snippet.lower()
                if not any(term in content_lower for term in ["put", "call", "option", "premium"]):
                    continue

            formatted.append(
                {
                    "content": lesson.snippet[:500] + "..."
                    if len(lesson.snippet) > 500
                    else lesson.snippet,
                    "source": lesson.id,
                    "type": "lesson_learned",
                    "concepts": [],
                    "relevance": score,
                }
            )

        return formatted[:n_results]
    except ImportError:
        logger.warning("LessonsSearch not available - using basic file search")
        return []


def main():
    parser = argparse.ArgumentParser(description="Phil Town RAG Indexing")
    parser.add_argument("--rebuild", action="store_true", help="Full rebuild of local index")
    parser.add_argument("--update", action="store_true", help="Update with new content only")
    parser.add_argument("--query", type=str, help="Query the RAG")
    parser.add_argument("--options-only", action="store_true", help="Filter to options content")
    parser.add_argument("--stats", action="store_true", help="Show indexing stats")
    args = parser.parse_args()

    if args.query:
        results = query_rag(args.query, filter_options=args.options_only)
        print(f"\n🔍 Query: {args.query}\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['type']}] {r['source']} (relevance: {r['relevance']:.2f})")
            concepts = r.get("concepts", [])
            print(f"   Concepts: {', '.join(concepts[:3]) if concepts else 'none'}")
            print(f"   {r['content'][:200]}...")
            print()
        return

    if args.stats:
        cache = load_index_cache()
        print("\n📊 RAG Indexing Stats:")
        print(f"   Last updated: {cache.get('last_updated', 'never')}")
        print(f"   Files indexed: {len(cache.get('files', {}))}")
        return

    if args.rebuild or args.update:
        print("\n🔄 Indexing Phil Town knowledge base...")
        stats = index_all(rebuild=args.rebuild)

        print("\n✅ Indexing complete!")
        print(f"   Files processed: {stats['files']}")
        print(f"   Files skipped: {stats['skipped']}")
        print(f"   Total indexed: {stats['total_indexed']}")
        print("\n   By source:")
        for source, s in stats["sources"].items():
            if s["files"] > 0:
                print(f"     {source}: {s['files']} files")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
