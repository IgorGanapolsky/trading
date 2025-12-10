from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import MIGRATIONS_PATH, SQLITE_PATH, ensure_directories


@contextmanager
def _connection(path: Path):
    ensure_directories()
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def _normalize_as_of(as_of: datetime | str) -> tuple[str, str]:
    if isinstance(as_of, datetime):
        aware = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        return aware.date().isoformat(), aware.astimezone(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(as_of)
    except ValueError:
        parsed = datetime.strptime(as_of, "%Y-%m-%d")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.date().isoformat(), parsed.astimezone(timezone.utc).isoformat()


class SentimentSQLiteStore:
    """Wrapper around SQLite for structured sentiment snapshots."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or SQLITE_PATH
        self.apply_migrations()

    def apply_migrations(self) -> None:
        """Apply any pending SQL migrations."""
        migration_files = sorted(p for p in MIGRATIONS_PATH.glob("*.sql") if p.is_file())

        if not migration_files:
            return

        with _connection(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")
            }

            for migration in migration_files:
                if migration.name in applied:
                    continue

                with open(migration, encoding="utf-8") as handle:
                    sql = handle.read()

                conn.executescript(sql)
                conn.execute(
                    """
                    INSERT INTO schema_migrations (filename, applied_at)
                    VALUES (?, ?)
                    """,
                    (migration.name, datetime.utcnow().isoformat()),
                )
            conn.commit()

    def upsert_snapshot(
        self,
        *,
        source: str,
        ticker: str,
        snapshot_date: str,
        score: float,
        confidence: str,
        market_regime: str | None,
        summary: str,
        metadata: dict,
        created_at: str | None = None,
    ) -> None:
        """Insert or update a single sentiment snapshot."""
        created_ts = created_at or datetime.utcnow().isoformat()

        with _connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sentiment_snapshots (
                    source, ticker, snapshot_date, score, confidence,
                    market_regime, summary, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, ticker, snapshot_date) DO UPDATE SET
                    score=excluded.score,
                    confidence=excluded.confidence,
                    market_regime=excluded.market_regime,
                    summary=excluded.summary,
                    metadata=excluded.metadata,
                    created_at=excluded.created_at
                """,
                (
                    source,
                    ticker,
                    snapshot_date,
                    float(score),
                    confidence,
                    market_regime,
                    summary,
                    json.dumps(metadata),
                    created_ts,
                ),
            )
            conn.commit()

    def bulk_upsert(self, entries: Iterable[dict]) -> None:
        """Bulk upsert multiple snapshots."""
        with _connection(self.db_path) as conn:
            cursor = conn.cursor()
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO sentiment_snapshots (
                        source, ticker, snapshot_date, score, confidence,
                        market_regime, summary, metadata, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, ticker, snapshot_date) DO UPDATE SET
                        score=excluded.score,
                        confidence=excluded.confidence,
                        market_regime=excluded.market_regime,
                        summary=excluded.summary,
                        metadata=excluded.metadata,
                        created_at=excluded.created_at
                    """,
                    (
                        entry["source"],
                        entry["ticker"],
                        entry["snapshot_date"],
                        float(entry["score"]),
                        entry["confidence"],
                        entry.get("market_regime"),
                        entry["summary"],
                        json.dumps(entry.get("metadata", {})),
                        entry.get("created_at", datetime.utcnow().isoformat()),
                    ),
                )
            conn.commit()

    def fetch_latest_by_ticker(
        self,
        ticker: str,
        limit: int = 30,
        as_of: datetime | str | None = None,
    ) -> Iterable[sqlite3.Row]:
        """Fetch latest snapshots for a ticker with optional point-in-time filter."""
        filters = ["ticker = ?"]
        params: list[str] = [ticker.upper()]
        if as_of:
            date_cutoff, ts_cutoff = _normalize_as_of(as_of)
            filters.append("snapshot_date <= ?")
            params.append(date_cutoff)
            filters.append("created_at <= ?")
            params.append(ts_cutoff)

        where_clause = " AND ".join(filters)
        query = "\n".join(
            [
                "SELECT *",
                "FROM sentiment_snapshots",
                "WHERE " + where_clause,
                "ORDER BY snapshot_date DESC, created_at DESC",
                "LIMIT ?",
            ]
        )
        with _connection(self.db_path) as conn:
            cursor = conn.execute(query, (*params, limit))
            return cursor.fetchall()

    def fetch_by_source_date(
        self,
        *,
        source: str,
        snapshot_date: str,
    ) -> Iterable[sqlite3.Row]:
        """Fetch all snapshots for a given source and date."""
        with _connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT *
                FROM sentiment_snapshots
                WHERE source = ?
                  AND snapshot_date = ?
                ORDER BY ticker ASC
                """,
                (source, snapshot_date),
            )
            return cursor.fetchall()
