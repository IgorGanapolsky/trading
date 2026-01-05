#!/usr/bin/env python3
"""
Pre-Commit Hook: RAG Architecture Validation

Prevents regression to "half-assed" RAG implementation by ensuring
all RAG systems use proper vector databases (ChromaDB/LanceDB).

Lesson Learned: lesson_20251215_104602_0
Prevention: Always use proper vector databases from day 1.

Author: Trading System CTO
Created: 2025-12-15
"""

import sys
from pathlib import Path


def check_rag_architecture() -> tuple[int, list[str]]:
    """
    Verify RAG implementations use proper vector databases.

    Returns:
        Tuple of (exit_code, violations)
    """
    violations = []
    warnings = []

    # Check all RAG-related files
    rag_dir = Path("src/rag")
    if not rag_dir.exists():
        return 0, []

    rag_files = list(rag_dir.glob("*.py"))

    for file_path in rag_files:
        # Skip test files
        if file_path.name.startswith("test_"):
            continue

        # Skip init files
        if file_path.name == "__init__.py":
            continue

        content = file_path.read_text()

        # Check if this is a RAG class implementation
        has_rag_class = "class" in content and "RAG" in content.upper()

        if not has_rag_class:
            continue

        # Red flags: JSON-based RAG without vector DB
        uses_json_storage = (
            "json.load" in content or "json.dump" in content or '"json"' in content.lower()
        )
        uses_vector_db = "chromadb" in content.lower() or "lancedb" in content.lower()

        # Allow JSON if it's just for fallback/migration
        has_chromadb_fallback = "_chroma" in content or "_use_chromadb" in content

        if has_rag_class and uses_json_storage:
            # Get relative path safely
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = file_path

            if not uses_vector_db:
                violations.append(f"❌ {rel_path}: RAG implementation uses JSON without vector DB!")
            elif not has_chromadb_fallback:
                warnings.append(
                    f"⚠️  {rel_path}: RAG has vector DB but may not be using it properly"
                )

    # Check requirements file
    req_file = Path("requirements-minimal.txt")
    if req_file.exists():
        req_content = req_file.read_text()

        # ChromaDB should not be commented out
        if "# chromadb" in req_content:
            violations.append(
                "❌ requirements-minimal.txt: chromadb is commented out! "
                "This will cause regression to JSON fallback."
            )

        # ChromaDB should be present
        if "chromadb" not in req_content.lower():
            violations.append(
                "❌ requirements-minimal.txt: chromadb not found! RAG requires vector database."
            )

    # Print results
    if violations:
        print("\n" + "=" * 70)
        print("⚠️  RAG ARCHITECTURE REGRESSION DETECTED")
        print("=" * 70)
        print()
        for violation in violations:
            print(violation)
        print()
        print("All RAG implementations MUST use ChromaDB or LanceDB.")
        print("See: rag_knowledge/lessons_learned/ll_rag_half_assed_dec15.md")
        print()
        print("Fix:")
        print("  1. Use ChromaDB: from chromadb import PersistentClient")
        print("  2. Uncomment chromadb in requirements-minimal.txt")
        print("  3. Query RAG lessons before implementing RAG features")
        print("=" * 70)
        return 1, violations

    if warnings:
        print("\n⚠️  RAG Architecture Warnings (non-blocking):")
        for warning in warnings:
            print(f"  {warning}")
        print()

    print("✅ RAG Architecture Validation: PASSED")
    return 0, []


if __name__ == "__main__":
    exit_code, violations = check_rag_architecture()
    sys.exit(exit_code)
