"""
Sentiment RAG Store backed by SQLite.

Stores daily sentiment snapshots (from cached JSON files) as embeddings inside a
lightweight SQLite database. Retrieval performs cosine similarity computations
in-process which is sufficient for the current dataset size (< a few thousand
documents).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from .vector_db.embedder import NewsEmbedder, get_embedder

logger = logging.getLogger(__name__)

DEFAULT_SENTIMENT_DIR = Path("data/sentiment")
STORAGE_DIR = Path("data/rag")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = STORAGE_DIR / "sentiment_rag.db"


@dataclass
class SentimentDocument:
    """Simple container for RAG sentiment entries."""

    document_id: str
    text: str
    metadata: dict[str, str]


class SentimentRAGStore:
    """
    Lightweight sentiment vector store using SQLite for persistence.
    """

    def __init__(
        self,
        db_path: Path = DB_PATH,
        embedder: NewsEmbedder | None = None,
        sentiment_dir: Path = DEFAULT_SENTIMENT_DIR,
    ):
        self.db_path = Path(db_path)
        self.embedder = embedder or get_embedder()
        self.sentiment_dir = Path(sentiment_dir)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()

    # ------------------------------------------------------------------ #
    # Schema management
    # ------------------------------------------------------------------ #
    def _create_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiment_documents (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                sentiment_score REAL,
                confidence TEXT,
                market_regime TEXT,
                source_list TEXT,
                freshness TEXT,
                days_old INTEGER,
                document TEXT NOT NULL,
                embedding BLOB NOT NULL,
                embedding_dim INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #
    def upsert_documents(self, documents: Iterable[SentimentDocument]) -> int:
        docs = list(documents)
        if not docs:
            logger.info("No sentiment documents to upsert.")
            return 0

        embeddings = self.embedder.embed_batch([doc.text for doc in docs])
        now = datetime.utcnow().isoformat()

        with self.connection:
            for doc, embedding in zip(docs, embeddings):
                metadata = doc.metadata
                payload = (
                    doc.document_id,
                    metadata.get("ticker"),
                    metadata.get("published_date"),
                    metadata.get("sentiment_score"),
                    metadata.get("confidence"),
                    metadata.get("market_regime"),
                    metadata.get("source_list"),
                    metadata.get("freshness"),
                    metadata.get("days_old"),
                    doc.text,
                    embedding.astype(np.float32).tobytes(),
                    len(embedding),
                    now,
                )
                self.connection.execute(
                    """
                    INSERT INTO sentiment_documents (
                        id, ticker, snapshot_date, sentiment_score, confidence,
                        market_regime, source_list, freshness, days_old, document,
                        embedding, embedding_dim, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        ticker=excluded.ticker,
                        snapshot_date=excluded.snapshot_date,
                        sentiment_score=excluded.sentiment_score,
                        confidence=excluded.confidence,
                        market_regime=excluded.market_regime,
                        source_list=excluded.source_list,
                        freshness=excluded.freshness,
                        days_old=excluded.days_old,
                        document=excluded.document,
                        embedding=excluded.embedding,
                        embedding_dim=excluded.embedding_dim,
                        created_at=excluded.created_at;
                    """,
                    payload,
                )

        logger.info("Upserted %d sentiment documents into %s", len(docs), self.db_path)
        return len(docs)

    def ingest_from_cache(self, days: int = 30) -> int:
        documents = list(load_sentiment_documents(window_days=days, base_dir=self.sentiment_dir))
        return self.upsert_documents(documents)

    def reset(self) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM sentiment_documents;")

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    def query(
        self,
        query: str,
        ticker: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        query_embedding = self.embedder.embed_single(query).astype(np.float32)
        rows = self._fetch_rows(ticker=ticker)
        if not rows:
            return []

        embeddings = np.vstack([row.embedding for row in rows])
        similarities = embeddings @ query_embedding  # embeddings are normalized
        top_indices = similarities.argsort()[::-1][:top_k]

        results = []
        for idx in top_indices:
            row = rows[idx]
            results.append(
                {
                    "id": row.id,
                    "document": row.document,
                    "score": float(similarities[idx]),
                    "metadata": row.metadata_dict(),
                }
            )
        return results

    def get_ticker_history(self, ticker: str, limit: int = 10) -> list[dict]:
        rows = self._fetch_rows(ticker=ticker, limit=limit, order_by_date=True)
        return [
            {
                "id": row.id,
                "document": row.document,
                "score": float(row.sentiment_score or 0.0),
                "metadata": row.metadata_dict(),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _fetch_rows(
        self,
        ticker: str | None = None,
        limit: int | None = None,
        order_by_date: bool = False,
    ) -> list[SentimentRow]:
        sql = """
            SELECT id, ticker, snapshot_date, sentiment_score, confidence,
                   market_regime, source_list, freshness, days_old,
                   document, embedding, embedding_dim
            FROM sentiment_documents
        """
        params: tuple = ()
        if ticker:
            sql += " WHERE ticker = ?"
            params = (ticker.upper(),)
        if order_by_date:
            sql += " ORDER BY snapshot_date DESC"
        if limit:
            sql += " LIMIT ?"
            params = params + (limit,) if params else (limit,)

        cursor = self.connection.execute(sql, params)
        rows = [
            SentimentRow(
                id=row[0],
                ticker=row[1],
                snapshot_date=row[2],
                sentiment_score=row[3],
                confidence=row[4],
                market_regime=row[5],
                source_list=row[6],
                freshness=row[7],
                days_old=row[8],
                document=row[9],
                embedding=np.frombuffer(row[10], dtype=np.float32),
                embedding_dim=row[11],
            )
            for row in cursor.fetchall()
        ]
        return rows


@dataclass
class SentimentRow:
    id: str
    ticker: str
    snapshot_date: str
    sentiment_score: float | None
    confidence: str | None
    market_regime: str | None
    source_list: str | None
    freshness: str | None
    days_old: int | None
    document: str
    embedding: np.ndarray
    embedding_dim: int

    def metadata_dict(self) -> dict[str, str | None]:
        return {
            "ticker": self.ticker,
            "snapshot_date": self.snapshot_date,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "market_regime": self.market_regime,
            "source_list": self.source_list,
            "freshness": self.freshness,
            "days_old": self.days_old,
        }


# --------------------------------------------------------------------- #
# Document preparation
# --------------------------------------------------------------------- #


def load_sentiment_documents(
    window_days: int = 30,
    base_dir: Path = DEFAULT_SENTIMENT_DIR,
) -> Iterable[SentimentDocument]:
    if not base_dir.exists():
        logger.warning("Sentiment directory %s does not exist.", base_dir)
        return

    files = sorted(base_dir.glob("*.json"), reverse=True)
    seen_dates = set()

    for file_path in files:
        try:
            with open(file_path) as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.error("Failed to load sentiment file %s: %s", file_path, exc)
            continue

        date_str = payload.get("meta", {}).get("date")
        if not date_str:
            continue

        if date_str not in seen_dates:
            seen_dates.add(date_str)
        if len(seen_dates) > window_days:
            break

        sentiment_map = payload.get("sentiment_by_ticker", {})
        for ticker, ticker_data in sentiment_map.items():
            document_id = f"{date_str}-{ticker.upper()}"
            text = _render_document_text(ticker, date_str, payload, ticker_data)
            metadata = _build_metadata(ticker, date_str, payload, ticker_data)
            yield SentimentDocument(document_id, text, metadata)


def _render_document_text(ticker: str, date: str, meta: dict, ticker_data: dict) -> str:
    sources = ticker_data.get("sources", {})
    lines = [
        f"Date: {date}",
        f"Ticker: {ticker.upper()}",
        f"Aggregate sentiment score: {ticker_data.get('score', 'N/A')}",
        f"Confidence: {ticker_data.get('confidence', 'unknown')}",
        f"Market regime: {ticker_data.get('market_regime', 'neutral')}",
    ]

    for source_name, details in sources.items():
        parts = [f"Source {source_name}"]
        if "normalized_score" in details:
            parts.append(f"normalized {details['normalized_score']}")
        elif "raw_score" in details:
            parts.append(f"raw {details['raw_score']}")
        elif "score" in details:
            parts.append(f"score {details['score']}")
        if "mentions" in details:
            parts.append(f"mentions {details['mentions']}")
        if "confidence" in details:
            parts.append(f"confidence {details['confidence']}")
        lines.append(", ".join(parts))

    meta_section = meta.get("meta", {})
    lines.append(f"Freshness: {meta_section.get('freshness', 'unknown')}")
    if "sources" in meta_section:
        lines.append(f"Sources included: {', '.join(meta_section['sources'])}")

    return "\n".join(lines)


def _build_metadata(ticker: str, date: str, meta: dict, ticker_data: dict) -> dict[str, str]:
    meta_section = meta.get("meta", {})
    metadata = {
        "ticker": ticker.upper(),
        "published_date": _normalize_date(date),
        "sentiment_score": float(ticker_data.get("score", 0.0)),
        "confidence": ticker_data.get("confidence", "unknown"),
        "market_regime": ticker_data.get("market_regime", "neutral"),
        "freshness": meta_section.get("freshness", "unknown"),
        "days_old": meta_section.get("days_old", 0),
    }

    sources = ticker_data.get("sources", {})
    metadata["source_list"] = ",".join(sorted(sources.keys()))
    return metadata


def _normalize_date(date_str: str) -> str:
    try:
        return datetime.fromisoformat(date_str).date().isoformat()
    except ValueError:
        return date_str
