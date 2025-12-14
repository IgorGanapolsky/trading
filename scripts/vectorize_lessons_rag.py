#!/usr/bin/env python3
"""Vectorize lessons learned for RAG semantic search.

This script:
1. Reads all lessons from rag_knowledge/lessons_learned/
2. Parses them into the proper Lesson format
3. Computes embeddings using sentence-transformers (if available)
4. Saves to data/rag/lessons_learned.json in the correct format

Run locally to pre-compute embeddings (CI doesn't need sentence-transformers):
    python scripts/vectorize_lessons_rag.py

Reference: December 2025 - RAG vectorization fix
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Try to import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Will save without embeddings.")


def extract_section(content: str, section_name: str) -> str:
    """Extract a section from markdown content."""
    pattern = rf"## {section_name}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def parse_lesson_file(filepath: Path) -> Optional[dict]:
    """Parse a lesson learned markdown file into Lesson format."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Extract metadata from frontmatter-style content
        metadata = {
            "id": "",
            "date": "",
            "severity": "medium",
            "category": "",
        }

        # Parse metadata lines like **ID**: ll_020
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("**ID**:"):
                metadata["id"] = line.split(":", 1)[1].strip()
            elif line.startswith("**Date**:"):
                metadata["date"] = line.split(":", 1)[1].strip()
            elif line.startswith("**Severity**:"):
                metadata["severity"] = line.split(":", 1)[1].strip().lower()
            elif line.startswith("**Category**:"):
                metadata["category"] = line.split(":", 1)[1].strip()

        # Extract title from first H1
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else filepath.stem

        # Extract key sections
        executive_summary = extract_section(content, "Executive Summary")
        problem = extract_section(content, "The Problem.*") or extract_section(content, "Problem")
        evidence = extract_section(content, "The Evidence") or extract_section(content, "Evidence")
        root_cause = extract_section(content, "Root Cause.*") or extract_section(content, "Why.*")
        fix = (
            extract_section(content, "The Fix")
            or extract_section(content, "Fix")
            or extract_section(content, "Solution")
        )
        prevention = extract_section(content, "Prevention.*") or extract_section(
            content, "Key Takeaway.*"
        )

        # Build description from available sections
        description_parts = []
        if executive_summary:
            description_parts.append(executive_summary)
        if problem:
            description_parts.append(f"Problem: {problem[:500]}")
        if evidence:
            description_parts.append(f"Evidence: {evidence[:500]}")

        description = "\n\n".join(description_parts) if description_parts else content[:1000]

        # Extract tags (lines starting with #tag)
        tags = []
        tags_section = extract_section(content, "Tags")
        if tags_section:
            tags = [t.strip("#").strip() for t in tags_section.split() if t.startswith("#")]

        # Build Lesson dict
        lesson = {
            "id": metadata["id"] or f"lesson_{filepath.stem}",
            "timestamp": metadata["date"] or datetime.now().isoformat(),
            "category": metadata["category"].lower().replace(" ", "_").replace(",", "_")
            or "general",
            "title": title[:200],
            "description": description[:2000],
            "root_cause": (root_cause or problem)[:1000],
            "prevention": (prevention or fix)[:1000],
            "tags": tags[:10],
            "severity": metadata["severity"],
            "financial_impact": None,
            "symbol": None,
            "source_file": str(filepath),
        }

        return lesson

    except Exception as e:
        logger.error(f"Failed to parse {filepath}: {e}")
        return None


def compute_embedding(encoder, lesson: dict) -> list[float]:
    """Compute embedding for a lesson."""
    text = (
        f"{lesson['title']} {lesson['description']} {lesson['root_cause']} {lesson['prevention']}"
    )
    return encoder.encode(text).tolist()


def main():
    logger.info("=" * 60)
    logger.info("RAG LESSONS VECTORIZATION")
    logger.info("=" * 60)

    lessons_dir = Path("rag_knowledge/lessons_learned")
    output_path = Path("data/rag/lessons_learned.json")

    if not lessons_dir.exists():
        logger.error(f"Lessons directory not found: {lessons_dir}")
        return 1

    # Find all lesson files
    lesson_files = sorted(lessons_dir.glob("ll_*.md"))
    logger.info(f"Found {len(lesson_files)} lesson files")

    if not lesson_files:
        logger.warning("No lesson files found!")
        return 0

    # Initialize encoder if available
    encoder = None
    if EMBEDDINGS_AVAILABLE:
        try:
            logger.info("Loading sentence-transformers model...")
            encoder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")

    # Load existing lessons to preserve manually added ones
    existing_lessons = []
    existing_ids = set()
    if output_path.exists():
        try:
            with open(output_path) as f:
                existing_data = json.load(f)
            # Keep lessons that don't have source_file (manually added)
            for lesson in existing_data:
                if "source_file" not in lesson:
                    existing_lessons.append(lesson)
                    existing_ids.add(lesson.get("id", ""))
            logger.info(f"Preserving {len(existing_lessons)} manually added lessons")
        except Exception as e:
            logger.warning(f"Could not load existing lessons: {e}")

    # Parse all lesson files
    parsed_lessons = []
    for filepath in lesson_files:
        lesson = parse_lesson_file(filepath)
        if lesson and lesson["id"] not in existing_ids:
            # Compute embedding if encoder available
            if encoder:
                lesson["embedding"] = compute_embedding(encoder, lesson)
            parsed_lessons.append(lesson)
            logger.info(f"  Parsed: {filepath.name} -> {lesson['id']}")

    # Combine existing and new lessons
    all_lessons = existing_lessons + parsed_lessons

    # Recompute embeddings for lessons without them (if encoder available)
    if encoder:
        updated = 0
        for lesson in all_lessons:
            if "embedding" not in lesson or not lesson.get("embedding"):
                lesson["embedding"] = compute_embedding(encoder, lesson)
                updated += 1
        if updated:
            logger.info(f"  Computed embeddings for {updated} lessons without them")

    # Save to output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_lessons, f, indent=2)

    # Summary
    with_embeddings = sum(1 for l in all_lessons if l.get("embedding"))
    logger.info("-" * 60)
    logger.info(f"Total lessons: {len(all_lessons)}")
    logger.info(f"With embeddings: {with_embeddings}")
    logger.info(f"Saved to: {output_path}")

    if with_embeddings == 0:
        logger.warning("")
        logger.warning("NO EMBEDDINGS COMPUTED!")
        logger.warning("Install sentence-transformers: pip install sentence-transformers")
        logger.warning("Then re-run this script to vectorize lessons.")
        return 1

    logger.info("")
    logger.info("RAG vectorization complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
