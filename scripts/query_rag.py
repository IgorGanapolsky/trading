#!/usr/bin/env python3
"""
Query RAG System for Lessons Learned.

Usage:
    python3 scripts/query_rag.py "query string"
    python3 scripts/query_rag.py --tag "category"

This script provides a unified interface to query the RAG system for lessons learned.
It attempts to use the vector database (ChromaDB) if available, but falls back
to keyword search on markdown files if dependencies are missing.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]  # Log to stderr to keep stdout clean for results
)
logger = logging.getLogger("query_rag")

def keyword_search(query: str, lessons_dir: Path) -> List[Dict[str, Any]]:
    """Fallback: Search markdown files for keywords."""
    results = []
    query_terms = query.lower().split()
    
    if not lessons_dir.exists():
        logger.warning(f"Lessons directory not found: {lessons_dir}")
        return []

    for md_file in lessons_dir.glob("*.md"):
        try:
            content = md_file.read_text(errors="replace")
            content_lower = content.lower()
            
            # Simple scoring: count matching terms
            score = sum(1 for term in query_terms if term in content_lower)
            
            if score > 0:
                results.append({
                    "document": content,
                    "metadata": {"source": md_file.name},
                    "score": score
                })
        except Exception as e:
            logger.error(f"Error reading {md_file}: {e}")
            
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:5]

def main():
    parser = argparse.ArgumentParser(description="Query RAG Lessons Learned")
    parser.add_argument("query", help="Natural language query or keywords")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    # 1. Try to use UnifiedRAG (ChromaDB)
    try:
        from src.rag.unified_rag import UnifiedRAG, CHROMA_AVAILABLE
        
        if CHROMA_AVAILABLE:
            logger.info("Using UnifiedRAG (ChromaDB)")
            rag = UnifiedRAG()
            results = rag.query_lessons(args.query, n_results=args.limit)
            
            # Print results
            print(f"\nFound {len(results['documents'][0])} lessons for: '{args.query}'\n")
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                print(f"--- Lesson {i+1} ---")
                print(f"File: {meta.get('source', 'Unknown')}")
                print(f"Content: {doc[:300]}...") # Truncate for readability
                print("-" * 40)
            return 0
        else:
            logger.warning("ChromaDB not available, falling back to keyword search.")
            
    except ImportError:
        logger.warning("Could not import UnifiedRAG, falling back to keyword search.")
    except Exception as e:
        logger.error(f"UnifiedRAG failed: {e}")
        logger.info("Falling back to keyword search.")

    # 2. Fallback to Keyword Search
    lessons_dir = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
    results = keyword_search(args.query, lessons_dir)
    
    if not results:
        print(f"No lessons found for: '{args.query}'")
        return 0
        
    print(f"\n[Fallback] Found {len(results)} lessons for: '{args.query}'\n")
    for i, res in enumerate(results):
        print(f"--- Lesson {i+1} ---")
        print(f"File: {res['metadata']['source']}")
        print(f"Content: {res['document'][:300]}...")
        print("-" * 40)

    return 0

if __name__ == "__main__":
    sys.exit(main())
