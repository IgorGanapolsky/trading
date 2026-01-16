#!/usr/bin/env python3
"""Sync ALL lessons from rag_knowledge/lessons_learned/ to Vertex AI RAG corpus.

CEO Directive (Jan 16, 2026): "Do the optimization" - populate Vertex AI corpus
so queries use semantic search instead of falling back to local keyword search.

This script:
1. Reads all .md files from rag_knowledge/lessons_learned/
2. Parses lesson metadata (ID, title, severity, category)
3. Uploads each lesson to Vertex AI RAG corpus via add_lesson()

Usage:
    python3 scripts/sync_lessons_to_vertex_rag.py
    python3 scripts/sync_lessons_to_vertex_rag.py --dry-run
    python3 scripts/sync_lessons_to_vertex_rag.py --limit 10
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Path to lessons
LESSONS_DIR = Path("rag_knowledge/lessons_learned")


def parse_lesson_file(filepath: Path) -> dict | None:
    """Parse a lesson markdown file and extract metadata."""
    try:
        content = filepath.read_text(encoding="utf-8")
        
        # Extract lesson ID from filename or content
        lesson_id = filepath.stem
        
        # Try to extract from content
        id_match = re.search(r'\*\*ID\*\*:\s*(\S+)', content)
        if id_match:
            lesson_id = id_match.group(1)
        
        # Extract title from first # heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else filepath.stem
        
        # Extract severity
        severity_match = re.search(r'\*\*Severity\*\*:\s*(\w+)', content, re.IGNORECASE)
        severity = severity_match.group(1).upper() if severity_match else "MEDIUM"
        
        # Extract category
        category_match = re.search(r'\*\*Category\*\*:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
        category = category_match.group(1).strip() if category_match else "trading"
        
        return {
            "lesson_id": lesson_id,
            "title": title,
            "content": content,
            "severity": severity,
            "category": category,
            "filepath": str(filepath),
        }
    except Exception as e:
        logger.error(f"Failed to parse {filepath}: {e}")
        return None


def sync_lessons_to_vertex_rag(dry_run: bool = False, limit: int | None = None) -> dict:
    """Sync all lessons to Vertex AI RAG corpus."""
    
    # Find all lesson files
    if not LESSONS_DIR.exists():
        logger.error(f"Lessons directory not found: {LESSONS_DIR}")
        return {"success": False, "error": "Directory not found"}
    
    lesson_files = sorted(LESSONS_DIR.glob("*.md"))
    total_files = len(lesson_files)
    logger.info(f"Found {total_files} lesson files")
    
    if limit:
        lesson_files = lesson_files[:limit]
        logger.info(f"Limited to {limit} files")
    
    if dry_run:
        logger.info("DRY RUN - no changes will be made")
    
    # Initialize Vertex AI RAG
    if not dry_run:
        try:
            from src.rag.vertex_rag import VertexRAG
            rag = VertexRAG()
            if not rag._initialized:
                logger.error("Vertex AI RAG not initialized - check credentials")
                return {"success": False, "error": "RAG not initialized"}
            logger.info(f"✅ Connected to Vertex AI RAG corpus: {rag._corpus.name}")
        except ImportError as e:
            logger.error(f"Failed to import VertexRAG: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Failed to initialize VertexRAG: {e}")
            return {"success": False, "error": str(e)}
    
    # Process each lesson
    results = {
        "total": len(lesson_files),
        "synced": 0,
        "skipped": 0,
        "failed": 0,
        "lessons": [],
    }
    
    for i, filepath in enumerate(lesson_files, 1):
        logger.info(f"[{i}/{len(lesson_files)}] Processing: {filepath.name}")
        
        # Parse lesson
        lesson = parse_lesson_file(filepath)
        if not lesson:
            results["failed"] += 1
            continue
        
        if dry_run:
            logger.info(f"  Would sync: {lesson['lesson_id']} - {lesson['title'][:50]}...")
            results["synced"] += 1
            results["lessons"].append(lesson["lesson_id"])
            continue
        
        # Upload to Vertex AI RAG
        try:
            success = rag.add_lesson(
                lesson_id=lesson["lesson_id"],
                title=lesson["title"],
                content=lesson["content"],
                severity=lesson["severity"],
                category=lesson["category"],
            )
            
            if success:
                logger.info(f"  ✅ Synced: {lesson['lesson_id']}")
                results["synced"] += 1
                results["lessons"].append(lesson["lesson_id"])
            else:
                logger.warning(f"  ❌ Failed to sync: {lesson['lesson_id']}")
                results["failed"] += 1
                
        except Exception as e:
            logger.error(f"  ❌ Error syncing {lesson['lesson_id']}: {e}")
            results["failed"] += 1
    
    results["success"] = results["failed"] == 0
    return results


def main():
    parser = argparse.ArgumentParser(description="Sync lessons to Vertex AI RAG")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually sync, just show what would happen")
    parser.add_argument("--limit", type=int, help="Limit number of lessons to sync")
    args = parser.parse_args()
    
    print("=" * 70)
    print("VERTEX AI RAG LESSON SYNC")
    print("=" * 70)
    print()
    
    results = sync_lessons_to_vertex_rag(dry_run=args.dry_run, limit=args.limit)
    
    print()
    print("=" * 70)
    print("SYNC RESULTS")
    print("=" * 70)
    print(f"Total lessons:  {results.get('total', 0)}")
    print(f"Synced:         {results.get('synced', 0)}")
    print(f"Failed:         {results.get('failed', 0)}")
    print()
    
    if results.get("success"):
        print("✅ SYNC COMPLETE")
        return 0
    else:
        print(f"❌ SYNC FAILED: {results.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
