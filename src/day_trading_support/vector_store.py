"""Vector store wrapper for day-trading resource summaries."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Iterable, Optional

try:  # pragma: no cover - optional dependency
    import chromadb
    from chromadb.api import Collection
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except Exception:  # pragma: no cover - degrade gracefully
    chromadb = None
    Collection = None  # type: ignore

RAG_ROOT = Path(os.getenv("SENTIMENT_RAG_ROOT", "data/rag")).resolve()
VECTOR_PATH = RAG_ROOT / "vector_store"
EMBEDDING_MODEL = os.getenv(
    "SENTIMENT_EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)


def ensure_directories() -> None:
    RAG_ROOT.mkdir(parents=True, exist_ok=True)
    VECTOR_PATH.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


class ResourceVectorStore:
    """Dedicated Chroma collection for resource insights."""

    COLLECTION_NAME = "day_trading_resources"

    def __init__(self, path: Optional[str] = None) -> None:
        ensure_directories()
        self.path = path or str(VECTOR_PATH)
        self._collection: Optional[Collection] = None
        if chromadb is None:
            logger.warning(
                "chromadb unavailable; resource embeddings will be skipped"
            )
            return
        client = chromadb.PersistentClient(  # type: ignore[call-arg]
            path=self.path,
            settings=Settings(anonymized_telemetry=False),
        )
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self._collection = client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=embedding_function,
            metadata={"description": "Day-trading resource knowledge base"},
        )

    def upsert_documents(self, docs: Iterable[Dict]) -> None:
        if self._collection is None:
            return
        doc_list = list(docs)
        if not doc_list:
            return
        ids = [doc["id"] for doc in doc_list]
        texts = [doc["text"] for doc in doc_list]
        metadata = [doc.get("metadata", {}) for doc in doc_list]
        try:
            self._collection.delete(ids=ids)
        except Exception:  # pragma: no cover - tolerable if not indexed yet
            pass
        self._collection.add(ids=ids, documents=texts, metadatas=metadata)
