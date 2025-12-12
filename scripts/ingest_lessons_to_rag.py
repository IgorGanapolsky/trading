#!/usr/bin/env python3
"""Ingest lessons learned into the RAG vector store.

This script reads all lessons learned from rag_knowledge/lessons_learned/
and ingests them into the vector store so they can be retrieved during
trading decisions.

Usage:
    python scripts/ingest_lessons_to_rag.py
    python scripts/ingest_lessons_to_rag.py --specific ll_019
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_lesson_metadata(content: str) -> dict:
    """Extract metadata from lesson learned markdown."""
    metadata = {
        "id": "",
        "date": "",
        "severity": "",
        "category": "",
        "impact": "",
        "tags": [],
    }

    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("**ID**:"):
            metadata["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("**Date**:"):
            metadata["date"] = line.split(":", 1)[1].strip()
        elif line.startswith("**Severity**:"):
            metadata["severity"] = line.split(":", 1)[1].strip()
        elif line.startswith("**Category**:"):
            metadata["category"] = line.split(":", 1)[1].strip()
        elif line.startswith("**Impact**:"):
            metadata["impact"] = line.split(":", 1)[1].strip()
        elif line.startswith("#") and not line.startswith("# "):
            # Tags line like #filters #gates #configuration
            tags = [t.strip("#").strip() for t in line.split() if t.startswith("#")]
            metadata["tags"] = tags

    return metadata


def chunk_lesson(content: str, max_chunk_size: int = 1000) -> list[dict]:
    """Split lesson into chunks for embedding."""
    chunks = []
    sections = content.split("\n## ")

    current_chunk = ""
    for i, section in enumerate(sections):
        if i > 0:
            section = "## " + section

        if len(current_chunk) + len(section) < max_chunk_size:
            current_chunk += section + "\n"
        else:
            if current_chunk.strip():
                chunks.append({"text": current_chunk.strip()})
            current_chunk = section + "\n"

    if current_chunk.strip():
        chunks.append({"text": current_chunk.strip()})

    return chunks


def ingest_lesson(lesson_path: Path, rag_store_path: Path) -> bool:
    """Ingest a single lesson into the RAG store."""
    try:
        content = lesson_path.read_text(encoding="utf-8")
        metadata = parse_lesson_metadata(content)

        # Create document ID from file hash
        doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]

        document = {
            "id": doc_id,
            "source": str(lesson_path),
            "type": "lesson_learned",
            "metadata": metadata,
            "content": content,
            "chunks": chunk_lesson(content),
            "ingested_at": datetime.utcnow().isoformat(),
        }

        # Load existing store
        store_file = rag_store_path / "lessons_learned.json"
        existing = []
        if store_file.exists():
            try:
                existing = json.loads(store_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []

        # Check for duplicates
        existing_ids = {d["id"] for d in existing}
        if doc_id in existing_ids:
            logger.info(f"  Skipping {lesson_path.name} (already ingested)")
            return False

        existing.append(document)

        # Save updated store
        store_file.parent.mkdir(parents=True, exist_ok=True)
        store_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        logger.info(f"  ✅ Ingested {lesson_path.name} ({len(document['chunks'])} chunks)")
        return True

    except Exception as e:
        logger.error(f"  ❌ Failed to ingest {lesson_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ingest lessons learned into RAG")
    parser.add_argument("--specific", help="Ingest only lessons matching this pattern")
    parser.add_argument(
        "--rag-path",
        default="data/rag",
        help="Path to RAG store directory",
    )
    args = parser.parse_args()

    lessons_dir = Path("rag_knowledge/lessons_learned")
    rag_store_path = Path(args.rag_path)

    if not lessons_dir.exists():
        logger.error(f"Lessons directory not found: {lessons_dir}")
        return 1

    # Find lesson files
    pattern = f"*{args.specific}*.md" if args.specific else "ll_*.md"
    lesson_files = sorted(lessons_dir.glob(pattern))

    if not lesson_files:
        logger.warning(f"No lesson files found matching pattern: {pattern}")
        return 0

    logger.info(f"Found {len(lesson_files)} lesson files")
    logger.info(f"RAG store path: {rag_store_path}")
    logger.info("-" * 40)

    ingested = 0
    for lesson_file in lesson_files:
        if ingest_lesson(lesson_file, rag_store_path):
            ingested += 1

    logger.info("-" * 40)
    logger.info(f"Ingested {ingested} new lessons into RAG store")

    return 0


if __name__ == "__main__":
    sys.exit(main())
