#!/usr/bin/env python3
"""Backfill/rebuild trading lessons into SQLite FTS5.

Usage:
    python scripts/sync_lessons_to_sqlite_fts.py
    python scripts/sync_lessons_to_sqlite_fts.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.lesson_store import ensure_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync markdown lessons → SQLite FTS5")
    parser.add_argument("--force", action="store_true", help="Force full rebuild")
    parser.add_argument("--db", type=Path, default=None, help="Optional DB path")
    args = parser.parse_args()
    result = ensure_index(args.db, force=args.force)
    print(result)
    return 0 if result.get("count", 0) >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
