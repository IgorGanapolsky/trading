from __future__ import annotations

from collections.abc import Iterable

import chromadb
from chromadb.api import Collection
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from .config import EMBEDDING_MODEL, VECTOR_PATH, ensure_directories


class SentimentVectorStore:
    """Wrapper around Chroma for storing sentiment embeddings."""

    COLLECTION_NAME = "sentiment_documents"

    def __init__(self, path: str | None = None) -> None:
        ensure_directories()
        self.path = path or str(VECTOR_PATH)
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

    def upsert_documents(self, docs: Iterable[dict]) -> None:
        """Upsert sentiment documents into the vector store."""
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
    ) -> dict:
        """Query the vector store with optional ticker filter."""
        where = {"ticker": ticker} if ticker else None
        return self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )
