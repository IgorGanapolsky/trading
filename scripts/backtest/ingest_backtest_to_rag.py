#!/usr/bin/env python3
"""
Ingest Backtest Results to Local RAG

Reads backtest lessons and prepares them for LanceDB indexing
via local markdown output.

Usage:
    python scripts/backtest/ingest_backtest_to_rag.py --lessons-dir data/backtests
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def find_lesson_files(lessons_dir: Path) -> list[Path]:
    """Find all lesson JSON files in directory."""
    if not lessons_dir.exists():
        return []

    return list(lessons_dir.glob("*_lessons_*.json")) + list(lessons_dir.glob("*_lesson_*.json"))


def load_lessons(file_path: Path) -> list[dict]:
    """Load lessons from JSON file."""
    with open(file_path) as f:
        data = json.load(f)

    # Handle both list and single lesson formats
    if isinstance(data, list):
        return data
    return [data]


def format_lesson_for_rag(lesson: dict) -> str:
    """Format lesson content for RAG ingestion."""
    content = lesson.get("content", "")

    # Add metadata as structured header
    header = f"""
# {lesson.get("title", "Backtest Lesson")}

**Type**: {lesson.get("type", "UNKNOWN")}
**Generated**: {lesson.get("metadata", {}).get("timestamp", datetime.now().isoformat())}

---

"""
    return header + content


def save_for_manual_ingestion(lessons: list[dict], output_dir: Path) -> Path:
    """
    Save lessons in format ready for manual RAG ingestion.
    This is a fallback when direct API access isn't available.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"rag_ready_lessons_{timestamp}.md"

    with open(output_path, "w") as f:
        f.write("# Backtest Lessons for RAG Ingestion\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")

        for lesson in lessons:
            f.write(format_lesson_for_rag(lesson))
            f.write("\n\n---\n\n")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Ingest backtest lessons to RAG")
    parser.add_argument(
        "--lessons-dir",
        type=str,
        default="data/backtests",
        help="Directory with lesson files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/rag_staging",
        help="Output for manual ingestion",
    )

    args = parser.parse_args()

    lessons_dir = Path(args.lessons_dir)

    # Find lesson files
    lesson_files = find_lesson_files(lessons_dir)

    if not lesson_files:
        print(f"⚠️ No lesson files found in {lessons_dir}")
        sys.exit(0)

    print(f"📂 Found {len(lesson_files)} lesson files")

    # Load all lessons
    all_lessons = []
    for file_path in lesson_files:
        lessons = load_lessons(file_path)
        all_lessons.extend(lessons)
        print(f"  📄 Loaded {len(lessons)} lessons from {file_path.name}")

    print(f"\n📊 Total lessons to process: {len(all_lessons)}")

    # Save for local ingestion
    output_path = save_for_manual_ingestion(all_lessons, Path(args.output))
    print(f"\n📁 Manual ingestion file saved to: {output_path}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 RAG INGESTION SUMMARY")
    print("=" * 50)
    print(f"Lesson files processed: {len(lesson_files)}")
    print(f"Total lessons: {len(all_lessons)}")
    print("Direct RAG ingestion: skipped (local only)")
    print(f"Manual ingestion file: {output_path}")
    print("=" * 50)

    # List lesson types
    types = {}
    for lesson in all_lessons:
        t = lesson.get("type", "UNKNOWN")
        types[t] = types.get(t, 0) + 1

    print("\nLesson types:")
    for t, count in sorted(types.items()):
        print(f"  - {t}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
