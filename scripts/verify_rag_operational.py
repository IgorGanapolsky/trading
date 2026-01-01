#!/usr/bin/env python3
"""
RAG Operational Verification - Fails if RAG is not working properly.

This script is designed to be run as a startup hook to BLOCK sessions
if RAG is broken. No silent failures allowed.

Exit codes:
  0 = RAG is operational
  1 = RAG is broken - DO NOT PROCEED
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_chromadb_installed() -> tuple[bool, str]:
    """Verify chromadb package is actually installed."""
    try:
        import chromadb
        return True, f"chromadb v{chromadb.__version__}"
    except ImportError:
        return False, "chromadb NOT INSTALLED - run: pip install chromadb"


def verify_vector_db_has_documents() -> tuple[bool, str]:
    """Verify vector database has documents indexed."""
    try:
        import chromadb
        from chromadb.config import Settings

        db_path = Path("data/vector_db")
        if not db_path.exists():
            return False, "Vector DB path does not exist"

        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )

        collection = client.get_or_create_collection(name="phil_town_rag")
        count = collection.count()

        if count == 0:
            return False, "Vector DB is EMPTY (0 documents)"
        elif count < 100:
            return False, f"Vector DB has only {count} docs (expected 500+)"

        return True, f"Vector DB has {count} documents"
    except Exception as e:
        return False, f"Vector DB error: {e}"


def verify_semantic_search_works() -> tuple[bool, str]:
    """Verify semantic search actually returns relevant results."""
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path="data/vector_db",
            settings=Settings(anonymized_telemetry=False),
        )
        collection = client.get_or_create_collection(name="phil_town_rag")

        # Test query that SHOULD find results about capital protection
        test_query = "losing money protect capital"
        results = collection.query(
            query_texts=[test_query],
            n_results=3,
            include=["documents", "distances"],
        )

        if not results or not results.get("ids") or not results["ids"][0]:
            return False, f"Query '{test_query}' returned no results"

        # Check that results are actually relevant (low distance = high similarity)
        distances = results.get("distances", [[]])[0]
        if distances and min(distances) > 1.5:  # Threshold for relevance
            return False, f"Results not relevant (distance: {min(distances):.2f})"

        # Verify we found something about money/capital/loss
        docs = results.get("documents", [[]])[0]
        relevant_keywords = ["money", "loss", "capital", "protect", "rule", "don't lose"]
        found_relevant = any(
            any(kw.lower() in doc.lower() for kw in relevant_keywords)
            for doc in docs if doc
        )

        if not found_relevant:
            return False, "Search returned irrelevant results (semantic search may be broken)"

        return True, f"Semantic search working (found {len(results['ids'][0])} results)"
    except Exception as e:
        return False, f"Semantic search error: {e}"


def verify_lessons_search_class() -> tuple[bool, str]:
    """Verify the LessonsSearch class works correctly."""
    try:
        from src.rag.lessons_search import LessonsSearch

        ls = LessonsSearch()

        # Check it loaded lessons
        if ls.count() == 0:
            return False, "LessonsSearch loaded 0 lessons"

        # Check it connected to correct collection
        if ls.collection is None:
            return False, "LessonsSearch not connected to ChromaDB"

        doc_count = ls.collection.count()
        if doc_count == 0:
            return False, "LessonsSearch connected to EMPTY collection"

        # Test the search method
        results = ls.search("blind trading catastrophe", top_k=3)
        if not results:
            return False, "LessonsSearch.search() returned no results"

        # Verify results have correct format
        lesson, score = results[0]
        if not hasattr(lesson, 'id') or not hasattr(lesson, 'severity'):
            return False, "LessonsSearch results have wrong format"

        return True, f"LessonsSearch OK ({ls.count()} lessons, {doc_count} vectors)"
    except Exception as e:
        return False, f"LessonsSearch error: {e}"


def main():
    """Run all RAG verification checks."""
    print("=" * 60)
    print("RAG OPERATIONAL VERIFICATION")
    print("=" * 60)

    checks = [
        ("ChromaDB Installed", verify_chromadb_installed),
        ("Vector DB Has Documents", verify_vector_db_has_documents),
        ("Semantic Search Works", verify_semantic_search_works),
        ("LessonsSearch Class", verify_lessons_search_class),
    ]

    all_passed = True
    results = []

    for name, check_fn in checks:
        try:
            passed, message = check_fn()
        except Exception as e:
            passed, message = False, f"Unexpected error: {e}"

        status = "✅" if passed else "❌"
        results.append((name, passed, message))
        print(f"{status} {name}: {message}")

        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("✅ RAG IS OPERATIONAL - Safe to proceed")
        return 0
    else:
        print("❌ RAG IS BROKEN - DO NOT TRADE")
        print("")
        print("Fix commands:")
        print("  pip install chromadb")
        print("  python3 scripts/vectorize_rag_knowledge.py --rebuild")
        return 1


if __name__ == "__main__":
    sys.exit(main())
