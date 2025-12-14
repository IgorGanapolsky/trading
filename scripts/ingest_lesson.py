from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.rag.vector_db.chroma_client import get_rag_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ingest_lesson(
    lesson_path: Path,
    *,
    source: str,
    date: str,
    category: str,
    severity: str,
    query_smoke_test: str | None = None,
) -> int:
    db = get_rag_db()

    if not lesson_path.exists():
        logger.error("Lesson file not found: %s", lesson_path)
        return 2

    content = _read_text(lesson_path)
    if not content.strip():
        logger.error("Lesson file is empty: %s", lesson_path)
        return 2

    doc = content
    metadata = {
        "ticker": "LESSON_LEARNED",
        "source": source,
        "date": date,
        "category": category,
        "severity": severity,
        "path": str(lesson_path),
    }
    doc_id = f"lesson_{lesson_path.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    logger.info("Ingesting lesson into vector store: %s", lesson_path)
    result = db.add_documents(documents=[doc], metadatas=[metadata], ids=[doc_id])

    if result.get("status") != "success":
        logger.error("Failed to ingest: %s", result.get("message", result))
        return 1

    logger.info("✅ Lesson learned ingested successfully (%s)", doc_id)

    if query_smoke_test:
        logger.info("Verifying retrieval with query: %r", query_smoke_test)
        results = db.query(query_smoke_test, n_results=1)
        docs = results.get("documents") if isinstance(results, dict) else None
        if docs:
            logger.info("Retrieval verified: %s...", str(docs[0])[:100])
        else:
            logger.warning("Could not retrieve ingested lesson immediately")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a lesson into the RAG vector store.")
    parser.add_argument(
        "--path",
        required=True,
        help="Path to lesson text/markdown file to ingest",
    )
    parser.add_argument("--source", default="internal_incident")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--category", default="lessons_learned")
    parser.add_argument("--severity", default="high")
    parser.add_argument(
        "--query-smoke-test",
        default=None,
        help="Optional query string to validate immediate retrieval",
    )
    args = parser.parse_args()

    return ingest_lesson(
        Path(args.path),
        source=args.source,
        date=args.date,
        category=args.category,
        severity=args.severity,
        query_smoke_test=args.query_smoke_test,
    )


if __name__ == "__main__":
    raise SystemExit(main())
