"""SQLite FTS5 lesson store for the trading defended RAG path.

Source of truth for searchable lesson rows. Markdown under
``rag_knowledge/lessons_learned/`` remains the human-editable corpus; this
module dual-writes / backfills into FTS5 for sub-ms ranked retrieval.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT / "data" / "rag" / "lessons.sqlite"
DEFAULT_KNOWLEDGE_DIR = ROOT / "rag_knowledge" / "lessons_learned"

_SEVERITY_RE = re.compile(
    r"\*\*severity\*\*\s*:\s*(critical|high|medium|low)"
    r"|severity\s*:\s*(critical|high|medium|low)",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_PREVENTION_RE = re.compile(
    r"##\s*(?:prevention|how to avoid|solution|takeaway)[^\n]*\n(.*?)(?=\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_TAGS_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class LessonRow:
    id: str
    title: str
    content: str
    severity: str
    prevention: str
    tags: list[str]
    source_path: str
    updated_at: str


def default_db_path() -> Path:
    return Path(DEFAULT_DB_PATH)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lessons (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'MEDIUM',
            prevention TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            source_path TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_lessons_severity ON lessons(severity);
        CREATE INDEX IF NOT EXISTS idx_lessons_updated ON lessons(updated_at);

        CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
            title,
            content,
            prevention,
            tags,
            content='lessons',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS lessons_ai AFTER INSERT ON lessons BEGIN
            INSERT INTO lessons_fts(rowid, title, content, prevention, tags)
            VALUES (
                new.rowid,
                new.title,
                new.content,
                COALESCE(new.prevention, ''),
                new.tags_json
            );
        END;

        CREATE TRIGGER IF NOT EXISTS lessons_ad AFTER DELETE ON lessons BEGIN
            INSERT INTO lessons_fts(lessons_fts, rowid, title, content, prevention, tags)
            VALUES (
                'delete',
                old.rowid,
                old.title,
                old.content,
                COALESCE(old.prevention, ''),
                old.tags_json
            );
        END;

        CREATE TRIGGER IF NOT EXISTS lessons_au AFTER UPDATE ON lessons BEGIN
            INSERT INTO lessons_fts(lessons_fts, rowid, title, content, prevention, tags)
            VALUES (
                'delete',
                old.rowid,
                old.title,
                old.content,
                COALESCE(old.prevention, ''),
                old.tags_json
            );
            INSERT INTO lessons_fts(rowid, title, content, prevention, tags)
            VALUES (
                new.rowid,
                new.title,
                new.content,
                COALESCE(new.prevention, ''),
                new.tags_json
            );
        END;
        """
    )
    conn.commit()


def parse_markdown_lesson(path: Path) -> LessonRow | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("Failed to read lesson %s: %s", path, exc)
        return None
    if not text.strip():
        return None

    title_m = _TITLE_RE.search(text)
    title = (title_m.group(1).strip() if title_m else path.stem)[:240]
    sev_m = _SEVERITY_RE.search(text)
    severity = "MEDIUM"
    if sev_m:
        severity = (sev_m.group(1) or sev_m.group(2) or "medium").upper()

    prev_m = _PREVENTION_RE.search(text)
    prevention = (prev_m.group(1).strip() if prev_m else "")[:2000]

    tags: list[str] = []
    if "## Tags" in text or "## tags" in text:
        tail = re.split(r"##\s*tags", text, flags=re.IGNORECASE)[-1]
        tags = _TAGS_RE.findall(tail)[:20]

    return LessonRow(
        id=path.stem,
        title=title,
        content=text,
        severity=severity,
        prevention=prevention,
        tags=tags,
        source_path=str(path),
        updated_at=datetime.now(UTC).isoformat(),
    )


def upsert_lesson(conn: sqlite3.Connection, lesson: LessonRow) -> None:
    conn.execute(
        """
        INSERT INTO lessons (id, title, content, severity, prevention, tags_json, source_path, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            content=excluded.content,
            severity=excluded.severity,
            prevention=excluded.prevention,
            tags_json=excluded.tags_json,
            source_path=excluded.source_path,
            updated_at=excluded.updated_at
        """,
        (
            lesson.id,
            lesson.title,
            lesson.content,
            lesson.severity,
            lesson.prevention,
            json.dumps(lesson.tags),
            lesson.source_path,
            lesson.updated_at,
        ),
    )
    conn.commit()


def upsert_feedback_lesson(
    conn: sqlite3.Connection,
    *,
    lesson_id: str,
    title: str,
    content: str,
    severity: str = "HIGH",
    prevention: str = "",
    tags: Optional[list[str]] = None,
) -> LessonRow:
    row = LessonRow(
        id=lesson_id,
        title=title[:240],
        content=content,
        severity=severity.upper(),
        prevention=prevention[:2000],
        tags=list(tags or ["feedback", "negative"]),
        source_path="feedback",
        updated_at=datetime.now(UTC).isoformat(),
    )
    upsert_lesson(conn, row)
    return row


def _sanitize_fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_\-]{2,}", query or "")
    if not terms:
        return ""
    # Phrase each token so FTS5 operators in user text cannot break MATCH.
    return " ".join(f'"{t}"' for t in terms[:24])


def search_fts(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 40,
    severity: str | None = None,
) -> list[dict[str, Any]]:
    fts_q = _sanitize_fts_query(query)
    if not fts_q:
        sql = "SELECT * FROM lessons"
        params: list[Any] = []
        if severity:
            sql += " WHERE severity = ?"
            params.append(severity.upper())
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    else:
        sql = """
            SELECT l.*, bm25(lessons_fts) AS rank
            FROM lessons_fts
            JOIN lessons l ON l.rowid = lessons_fts.rowid
            WHERE lessons_fts MATCH ?
        """
        params = [fts_q]
        if severity:
            sql += " AND l.severity = ?"
            params.append(severity.upper())
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS query failed (%s); falling back to LIKE", exc)
            like = f"%{(query or '').strip()}%"
            rows = conn.execute(
                """
                SELECT * FROM lessons
                WHERE content LIKE ? OR title LIKE ? OR prevention LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (like, like, like, limit),
            ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        tags = []
        try:
            tags = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []
        rank = float(row["rank"]) if "rank" in row else 0.0
        # bm25: lower is better; convert to a 0..1-ish score for fusion.
        score = 1.0 / (1.0 + max(0.0, rank + 10.0)) if rank else 0.5
        out.append(
            {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "severity": row["severity"],
                "prevention": row["prevention"] or "",
                "snippet": (row["content"] or "")[:500],
                "tags": tags,
                "source_path": row["source_path"] or "",
                "score": score,
                "fts_rank": rank,
                "backend": "sqlite-fts5",
            }
        )
    return out


def count_lessons(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM lessons").fetchone()
    return int(row["n"] if row else 0)


def backfill_from_markdown(
    conn: sqlite3.Connection,
    knowledge_dir: Path | None = None,
) -> dict[str, int]:
    directory = Path(knowledge_dir or DEFAULT_KNOWLEDGE_DIR)
    stats = {"files": 0, "upserted": 0, "skipped": 0}
    if not directory.exists():
        return stats
    for path in sorted(directory.glob("*.md")):
        stats["files"] += 1
        lesson = parse_markdown_lesson(path)
        if not lesson:
            stats["skipped"] += 1
            continue
        upsert_lesson(conn, lesson)
        stats["upserted"] += 1
    return stats


def ensure_index(
    db_path: Path | None = None,
    knowledge_dir: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Ensure FTS DB exists and is non-empty (backfill from markdown if needed)."""
    conn = connect(db_path)
    try:
        n = count_lessons(conn)
        if force or n == 0:
            stats = backfill_from_markdown(conn, knowledge_dir)
            try:
                conn.execute("INSERT INTO lessons_fts(lessons_fts) VALUES('rebuild')")
                conn.commit()
            except sqlite3.OperationalError:
                pass
            n = count_lessons(conn)
            return {"status": "backfilled", "count": n, **stats}
        return {"status": "ok", "count": n}
    finally:
        conn.close()
