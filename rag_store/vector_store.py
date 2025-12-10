from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

try:
    import chromadb
    from chromadb.api import Collection
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError:
    chromadb = None
    Collection = None
    Settings = None
    embedding_functions = None

from .config import EMBEDDING_MODEL, VECTOR_PATH, ensure_directories


class SentimentVectorStore:
    """Wrapper around Chroma for storing sentiment embeddings."""

    COLLECTION_NAME = "sentiment_documents"

    def __init__(self, path: str | None = None) -> None:
        ensure_directories()
        self.path = path or str(VECTOR_PATH)
        if chromadb:
            self._client = chromadb.PersistentClient(
                path=self.path,
                settings=Settings(anonymized_telemetry=False),
            )
            embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
            self._collection: Collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=embedding_function,
                metadata={"description": "Sentiment documents keyed by ticker/source/date"},
            )
        else:
            self._client = None
            self._collection = None

    def upsert_documents(self, docs: Iterable[dict]) -> None:
        """Upsert sentiment documents into the vector store."""
        if not self._collection:
            return

        documents = []
        metadatas = []
        ids = []

        docs = list(docs)
        if not docs:
            return

        for doc in docs:
            doc_id = doc["id"]
            # Remove existing entry if present to avoid duplicates
            self._collection.delete(ids=[doc_id])
            documents.append(doc["text"])
            metadatas.append(doc.get("metadata", {}))
            ids.append(doc_id)

        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def query(
        self,
        query_text: str,
        *,
        ticker: str | None = None,
        n_results: int = 5,
        as_of: datetime | str | None = None,
    ) -> dict:
        """Query the vector store with optional ticker filter."""
        if not self._collection:
            return {"documents": [], "metadatas": [], "distances": []}

        where = {}
        if ticker:
            where["ticker"] = ticker.upper()
        if as_of:
            date_cutoff, ts_cutoff = _normalize_as_of(as_of)
            where["snapshot_date"] = {"$lte": date_cutoff}
            where["created_at"] = {"$lte": ts_cutoff}
        where_clause = where or None
        return self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_clause,
        )


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
