#!/usr/bin/env python3
"""
Index Lessons Learned CLI

Command-line interface for indexing lessons learned markdown files
into a vector store for semantic search.

Usage:
    # Index all lessons
    python scripts/index_lessons_learned.py

    # Clear index and re-index
    python scripts/index_lessons_learned.py --clear

    # Search for lessons
    python scripts/index_lessons_learned.py --search "How to prevent CI failures?"

    # Show statistics
    python scripts/index_lessons_learned.py --stats

Features:
- Indexes all .md files from rag_knowledge/lessons_learned/
- Chunks by section (## headers)
- Generates embeddings (FastEmbed or TF-IDF)
- Stores in LanceDB vector database
- Provides search interface
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.lessons_indexer import LessonsIndexer
from src.rag.lessons_search import LessonsSearch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def index_lessons(clear: bool = False):
    """Index all lessons learned files."""
    print("\n" + "="*70)
    print("INDEXING LESSONS LEARNED")
    print("="*70)

    # Initialize indexer
    indexer = LessonsIndexer()

    # Clear if requested
    if clear:
        print("\nClearing existing index...")
        indexer.clear_index()

    # Index all lessons
    print("\nIndexing lessons from rag_knowledge/lessons_learned/...")
    stats = indexer.index_all_lessons()

    # Print results
    print("\n" + "="*70)
    print("INDEXING COMPLETE")
    print("="*70)
    print(f"Files indexed:     {stats['total_files']}")
    print(f"Chunks created:    {stats['total_chunks']}")
    print(f"Using FastEmbed:   {stats['using_fastembed']}")
    print(f"Using LanceDB:     {stats['using_lancedb']}")
    print(f"Using TF-IDF:      {stats['using_tfidf']}")
    print(f"Indexed at:        {stats['indexed_at']}")
    print("="*70 + "\n")

    # Verify indexing
    if stats['total_chunks'] == 0:
        print("⚠️  WARNING: No chunks were indexed!")
        print("   Check that lesson files exist in rag_knowledge/lessons_learned/")
        return False

    print("✓ Indexing successful!")
    return True


def search_lessons(query: str, top_k: int = 3):
    """Search indexed lessons."""
    print("\n" + "="*70)
    print(f"SEARCHING LESSONS: '{query}'")
    print("="*70)

    # Initialize search
    search = LessonsSearch()

    # Check if index exists
    stats = search.get_stats()
    if stats['total_chunks'] == 0:
        print("\n⚠️  No indexed lessons found!")
        print("   Run without --search to index lessons first.")
        return

    # Perform search
    results = search.query(query, top_k=top_k)

    if not results:
        print("\nNo results found.")
        return

    # Print results
    print(f"\nFound {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        print(f"[{i}] {result.lesson_file}")
        print(f"    Section: {result.section_title}")
        print(f"    Score:   {result.score:.3f}")

        if result.metadata:
            meta_str = ", ".join(f"{k}: {v}" for k, v in list(result.metadata.items())[:3])
            print(f"    Meta:    {meta_str}")

        # Print content excerpt
        content = result.content.replace('\n', ' ').strip()
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"    Content: {content}")
        print()

    print("="*70 + "\n")


def show_stats():
    """Show indexing statistics."""
    print("\n" + "="*70)
    print("LESSONS LEARNED INDEX STATISTICS")
    print("="*70)

    # Get indexer stats
    indexer = LessonsIndexer()
    indexer_stats = indexer.get_stats()

    # Get search stats
    search = LessonsSearch()
    search_stats = search.get_stats()

    print("\nIndexer Status:")
    print(f"  Total files:       {indexer_stats.get('total_files', 0)}")
    print(f"  Total chunks:      {indexer_stats.get('total_chunks', 0)}")
    print(f"  Last indexed:      {indexer_stats.get('indexed_at', 'Never')}")

    print("\nSearch Engine Status:")
    print(f"  Available chunks:  {search_stats['total_chunks']}")
    print(f"  Available files:   {search_stats['total_files']}")
    print(f"  Using FastEmbed:   {search_stats['using_fastembed']}")
    print(f"  Using LanceDB:     {search_stats['using_lancedb']}")
    print(f"  Using TF-IDF:      {search_stats['using_tfidf']}")

    # List indexed files
    if search_stats['total_files'] > 0:
        print("\nIndexed Files:")
        lessons = search.get_all_lessons()
        for lesson in lessons[:10]:  # Show first 10
            print(f"  - {lesson}")
        if len(lessons) > 10:
            print(f"  ... and {len(lessons) - 10} more")

    print("\n" + "="*70 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index and search lessons learned",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index all lessons
  python scripts/index_lessons_learned.py

  # Clear and re-index
  python scripts/index_lessons_learned.py --clear

  # Search for lessons
  python scripts/index_lessons_learned.py --search "How to prevent CI failures?"

  # Show statistics
  python scripts/index_lessons_learned.py --stats

  # Search with more results
  python scripts/index_lessons_learned.py --search "trading system failures" --top-k 5
        """
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing index before indexing'
    )

    parser.add_argument(
        '--search',
        type=str,
        metavar='QUERY',
        help='Search for lessons (instead of indexing)'
    )

    parser.add_argument(
        '--top-k',
        type=int,
        default=3,
        metavar='K',
        help='Number of search results to return (default: 3)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show indexing statistics'
    )

    args = parser.parse_args()

    try:
        # Handle different modes
        if args.stats:
            show_stats()
        elif args.search:
            search_lessons(args.search, top_k=args.top_k)
        else:
            # Default: index lessons
            success = index_lessons(clear=args.clear)
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
