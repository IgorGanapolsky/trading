"""
FAISS-based vector store for trade lessons RAG.

Embeds trade lessons and research into a searchable vector index.
Query at entry time to retrieve relevant past lessons for current market conditions.

Uses sentence-transformers MiniLM for embeddings (fast, good financial semantics).
Falls back to TF-IDF if sentence-transformers not available.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LESSONS_DIR = Path(__file__).parent.parent.parent / "data" / "rag_knowledge" / "lessons_learned"
INDEX_DIR = Path(__file__).parent.parent.parent / "data" / "rag_index"
JOURNAL_FILE = Path(__file__).parent.parent.parent / "data" / "trade_journal.jsonl"


class TradeRAG:
    """Vector store for trade lessons. Supports embed, index, and query."""

    def __init__(self):
        self.documents: list[dict] = []
        self.embeddings = None
        self.index = None
        self._embedder = None
        self._use_faiss = False
        self._init_embedder()

    def _init_embedder(self):
        """Initialize embedding model. Try sentence-transformers → TF-IDF fallback."""
        try:
            from sentence_transformers import SentenceTransformer

            # BGE-base-en-v1.5: 84.7% accuracy vs MiniLM's 56% (MTEB benchmark)
            self._embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
            self._use_faiss = True
            logger.info("RAG: Using BGE-base-en-v1.5 embeddings + FAISS")
        except ImportError:
            logger.info("RAG: sentence-transformers not available, using TF-IDF fallback")
            self._use_faiss = False

    def build_index(self):
        """Build vector index from all lessons and journal entries."""
        self.documents = []

        # Load markdown lessons
        if LESSONS_DIR.exists():
            for f in sorted(LESSONS_DIR.glob("*.md")):
                content = f.read_text(encoding="utf-8", errors="ignore")
                self.documents.append(
                    {
                        "id": f.stem,
                        "content": content,
                        "source": "lesson",
                        "path": str(f),
                    }
                )

        # Load journal entries as documents
        if JOURNAL_FILE.exists():
            for line in JOURNAL_FILE.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    text = (
                        f"Trade {entry.get('expiry', '?')}: {entry.get('outcome', '?')} "
                        f"${entry.get('pnl', 0):+.2f} ({entry.get('pnl_pct', 0):+.1f}%) "
                        f"Exit: {entry.get('exit_reason', '?')} DTE={entry.get('dte_at_exit', '?')} "
                        f"Credit: ${entry.get('credit_per_share', 0):.2f}"
                    )
                    self.documents.append(
                        {
                            "id": f"journal_{entry.get('expiry', 'unknown')}",
                            "content": text,
                            "source": "journal",
                            "metadata": entry,
                        }
                    )
                except json.JSONDecodeError:
                    continue

        if not self.documents:
            logger.info("RAG: no documents to index")
            return

        texts = [d["content"] for d in self.documents]

        if self._use_faiss and self._embedder is not None:
            self._build_faiss_index(texts)
        else:
            self._build_tfidf_index(texts)

        logger.info(f"RAG index built: {len(self.documents)} documents")

    def _build_faiss_index(self, texts: list[str]):
        """Build FAISS index from text embeddings."""
        import numpy as np

        try:
            import faiss
        except ImportError:
            # faiss-cpu fallback
            logger.info("RAG: FAISS not available, falling back to numpy cosine similarity")
            self.embeddings = self._embedder.encode(texts, convert_to_numpy=True)
            return

        embeddings = self._embedder.encode(texts, convert_to_numpy=True)
        self.embeddings = embeddings.astype(np.float32)

        # Normalize for cosine similarity
        faiss.normalize_L2(self.embeddings)
        dim = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # Inner product on normalized = cosine
        self.index.add(self.embeddings)

    def _build_tfidf_index(self, texts: list[str]):
        """TF-IDF fallback when sentence-transformers/FAISS not available."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
            self.embeddings = vectorizer.fit_transform(texts)
            self._vectorizer = vectorizer
        except ImportError:
            # Ultimate fallback: keyword matching
            self.embeddings = None
            logger.info("RAG: no vectorizer available, will use keyword matching")

    def query(self, question: str, top_k: int = 3) -> list[dict]:
        """Retrieve most relevant documents for a query.

        Args:
            question: Natural language query (e.g., "what happens when VIX spikes?")
            top_k: Number of results to return

        Returns:
            List of {id, content, score, source} dicts, highest relevance first.
        """
        if not self.documents:
            self.build_index()
        if not self.documents:
            return []

        if self.index is not None:
            return self._query_faiss(question, top_k)
        elif self.embeddings is not None and self._use_faiss and self._embedder is not None:
            return self._query_numpy_cosine(question, top_k)
        elif self.embeddings is not None:
            return self._query_tfidf(question, top_k)
        else:
            return self._query_keyword(question, top_k)

    def _query_faiss(self, question: str, top_k: int) -> list[dict]:
        import faiss
        import numpy as np

        q_emb = self._embedder.encode([question], convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(q_emb)
        scores, indices = self.index.search(q_emb, min(top_k, len(self.documents)))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                doc = self.documents[idx]
                results.append({**doc, "score": float(score)})
        return results

    def _query_numpy_cosine(self, question: str, top_k: int) -> list[dict]:
        import numpy as np

        q_emb = self._embedder.encode([question], convert_to_numpy=True)
        # Cosine similarity
        norms_q = np.linalg.norm(q_emb, axis=1, keepdims=True)
        norms_d = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        q_norm = q_emb / (norms_q + 1e-8)
        d_norm = self.embeddings / (norms_d + 1e-8)
        scores = (d_norm @ q_norm.T).flatten()

        top_idx = scores.argsort()[-top_k:][::-1]
        return [{**self.documents[i], "score": float(scores[i])} for i in top_idx]

    def _query_tfidf(self, question: str, top_k: int) -> list[dict]:
        q_vec = self._vectorizer.transform([question])
        scores = (self.embeddings @ q_vec.T).toarray().flatten()
        top_idx = scores.argsort()[-top_k:][::-1]
        return [{**self.documents[i], "score": float(scores[i])} for i in top_idx if scores[i] > 0]

    def _query_keyword(self, question: str, top_k: int) -> list[dict]:
        """Last resort: keyword overlap scoring."""
        keywords = set(question.lower().split())
        scored = []
        for doc in self.documents:
            words = set(doc["content"].lower().split())
            overlap = len(keywords & words)
            if overlap > 0:
                scored.append({**doc, "score": overlap / len(keywords)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


def query_lessons(question: str, top_k: int = 3) -> list[dict]:
    """Convenience function: query the RAG store."""
    rag = TradeRAG()
    rag.build_index()
    return rag.query(question, top_k)
