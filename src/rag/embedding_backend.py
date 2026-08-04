"""Local-first embedding and late-interaction primitives for trading RAG.

The production preference is a configurable BGE sentence-transformer.  When the
optional model dependency or cached weights are unavailable, retrieval remains
fully operational through a deterministic feature-hash dense encoder.  The
fallback is deliberately labelled as lexical-dense rather than semantic so
operators cannot mistake graceful degradation for neural retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
DEFAULT_DIMENSION = 512
QUERY_INSTRUCTION = "Represent this sentence for searching relevant trading risk lessons: "
PASSAGE_INSTRUCTION = "Trading risk lesson: "

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)?")
_DOMAIN_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bic\b", re.IGNORECASE), "iron condor"),
    (re.compile(r"\bdte\b", re.IGNORECASE), "days to expiration"),
    (re.compile(r"\bcsp\b", re.IGNORECASE), "cash secured put"),
    (re.compile(r"\bpcs\b", re.IGNORECASE), "bull put credit spread"),
    (re.compile(r"\bpdt\b", re.IGNORECASE), "pattern day trader"),
    (re.compile(r"\bput[- ]credit\b", re.IGNORECASE), "bull put credit spread"),
    (re.compile(r"\bstop[- ]loss\b", re.IGNORECASE), "maximum loss exit"),
)


def normalize_domain_text(text: str) -> str:
    """Normalize common trading aliases without changing the source document.

    Single left-to-right pass: once a span is replaced it is not rescanned, so
    expanding ``PCS`` to ``bull put credit spread`` does not re-trigger the
    ``put credit`` alias.
    """
    normalized = " ".join(str(text).split())
    if not normalized:
        return normalized
    # Prefer longer / more specific patterns first
    patterns = sorted(_DOMAIN_ALIASES, key=lambda item: len(item[0].pattern), reverse=True)
    out: list[str] = []
    i = 0
    while i < len(normalized):
        matched = False
        for pattern, replacement in patterns:
            m = pattern.match(normalized, i)
            if m:
                out.append(replacement)
                i = m.end()
                matched = True
                break
        if not matched:
            out.append(normalized[i])
            i += 1
    return "".join(out)


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_domain_text(text).lower())


@lru_cache(maxsize=16384)
def _token_ngrams(token: str) -> frozenset[str]:
    padded = f"^{token}$"
    return frozenset(padded[index : index + 3] for index in range(max(1, len(padded) - 2)))


def _token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_ngrams = _token_ngrams(left)
    right_ngrams = _token_ngrams(right)
    union = left_ngrams | right_ngrams
    if not union:
        return 0.0
    return len(left_ngrams & right_ngrams) / len(union)


def _l2_normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(value) ** 2 for value in vector))
    if norm <= 1e-12:
        return [0.0 for _ in vector]
    return [float(value) / norm for value in vector]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity in [0, 1], clipping negative hash collisions."""
    if not left or not right or len(left) != len(right):
        return 0.0
    score = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    return max(0.0, min(1.0, score))


@dataclass(frozen=True)
class EmbeddingModelConfig:
    """Versioned embedding choice and its domain-adaptation instructions."""

    model_name: str = DEFAULT_EMBEDDING_MODEL
    dimension: int = DEFAULT_DIMENSION
    query_instruction: str = QUERY_INSTRUCTION
    passage_instruction: str = PASSAGE_INSTRUCTION
    allow_model_download: bool = False


@dataclass(frozen=True)
class DenseSearchResult:
    document_id: str
    score: float
    rank: int


class EmbeddingBackend:
    """Encode passages with a cached sentence-transformer or feature hashing.

    ``TRADING_RAG_EMBED_BACKEND`` may be ``auto``, ``sentence-transformers``, or
    ``feature-hash``.  Model downloads are opt-in through
    ``TRADING_RAG_ALLOW_MODEL_DOWNLOAD=1``; CI and paper operations therefore do
    not unexpectedly perform network I/O.
    """

    def __init__(
        self,
        config: EmbeddingModelConfig | None = None,
        *,
        backend: str | None = None,
    ) -> None:
        allow_download = os.getenv("TRADING_RAG_ALLOW_MODEL_DOWNLOAD", "0").lower() in {
            "1",
            "true",
            "yes",
        }
        self.config = config or EmbeddingModelConfig(
            model_name=os.getenv("TRADING_RAG_EMBED_MODEL", DEFAULT_EMBEDDING_MODEL),
            dimension=int(os.getenv("TRADING_RAG_HASH_DIMENSION", str(DEFAULT_DIMENSION))),
            allow_model_download=allow_download,
        )
        self._requested_backend = (
            (backend or os.getenv("TRADING_RAG_EMBED_BACKEND", "auto")).strip().lower()
        )
        self._model: Any = None
        self._backend_type = "feature-hash"
        self._feature_hash_cache: dict[str, tuple[float, ...]] = {}
        self._semantic_cache: dict[str, tuple[float, ...]] = {}
        self._semantic_cache_lock = threading.RLock()
        self._initialize_model()

    @property
    def backend_type(self) -> str:
        return self._backend_type

    @property
    def model_identity(self) -> str:
        if self._backend_type == "sentence-transformers":
            return self.config.model_name
        return f"feature-hash-v1-{self.config.dimension}d"

    @property
    def is_semantic(self) -> bool:
        return self._backend_type == "sentence-transformers"

    def _initialize_model(self) -> None:
        if self._requested_backend == "feature-hash":
            return
        if self._requested_backend not in {"auto", "sentence-transformers"}:
            raise ValueError(f"Unsupported embedding backend: {self._requested_backend}")

        semantic_enabled = os.getenv("TRADING_RAG_ENABLE_SEMANTIC", "0").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if self._requested_backend == "auto" and not semantic_enabled:
            logger.info(
                "Semantic embeddings are opt-in; using deterministic feature-hash dense retrieval"
            )
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.config.model_name,
                device="cpu",
                local_files_only=not self.config.allow_model_download,
            )
            self._backend_type = "sentence-transformers"
            logger.info("RAG embeddings: %s", self.config.model_name)
        except Exception as exc:
            if self._requested_backend == "sentence-transformers":
                logger.warning(
                    "Requested embedding model unavailable (%s); using feature-hash dense fallback",
                    type(exc).__name__,
                )
            else:
                logger.info(
                    "Semantic embeddings unavailable (%s); using feature-hash dense fallback",
                    type(exc).__name__,
                )
            self._model = None
            self._backend_type = "feature-hash"

    @staticmethod
    def _hash_feature(feature: str, dimension: int) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, byteorder="big", signed=False)
        index = raw % dimension
        sign = 1.0 if (raw >> 8) & 1 else -1.0
        return index, sign

    def _feature_hash(self, text: str) -> tuple[float, ...]:
        cached = self._feature_hash_cache.get(text)
        if cached is not None:
            return cached
        dimension = self.config.dimension
        vector = [0.0] * dimension
        tokens = _tokens(text)
        if not tokens:
            return tuple(vector)

        features: list[tuple[str, float]] = []
        for token in tokens:
            features.append((f"w:{token}", 1.0))
            padded = f"^{token}$"
            for width in (3, 4, 5):
                for index in range(max(0, len(padded) - width + 1)):
                    features.append((f"c{width}:{padded[index : index + width]}", 0.35))
        for index in range(len(tokens) - 1):
            features.append((f"b:{tokens[index]}_{tokens[index + 1]}", 1.35))

        for feature, weight in features:
            bucket, sign = self._hash_feature(feature, dimension)
            vector[bucket] += sign * weight
        encoded = tuple(_l2_normalize(vector))
        with self._semantic_cache_lock:
            if len(self._feature_hash_cache) >= 8192:
                self._feature_hash_cache.pop(next(iter(self._feature_hash_cache)))
            self._feature_hash_cache[text] = encoded
        return encoded

    def encode_query(self, text: str) -> list[float]:
        normalized = normalize_domain_text(text)
        if self._model is None:
            return list(self._feature_hash(normalized))
        prepared = f"{self.config.query_instruction}{normalized}"
        return self._encode_semantic([prepared])[0]

    def encode_passages(self, texts: Iterable[str]) -> list[list[float]]:
        normalized = [normalize_domain_text(text) for text in texts]
        if self._model is None:
            return [list(self._feature_hash(text)) for text in normalized]
        prepared = [f"{self.config.passage_instruction}{text}" for text in normalized]
        return self._encode_semantic(prepared)

    def _encode_semantic(self, prepared_texts: Sequence[str]) -> list[list[float]]:
        """Batch missing model inputs once, then reuse corpus vectors across queries."""
        if self._model is None:
            raise RuntimeError("Semantic encoder requested without a loaded model")

        unique_missing = list(
            dict.fromkeys(text for text in prepared_texts if text not in self._semantic_cache)
        )
        if unique_missing:
            with self._semantic_cache_lock:
                missing = [text for text in unique_missing if text not in self._semantic_cache]
                if missing:
                    encoded = self._model.encode(
                        missing,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                    )
                    for text, row in zip(missing, encoded, strict=True):
                        self._semantic_cache[text] = tuple(float(value) for value in row.tolist())

        return [list(self._semantic_cache[text]) for text in prepared_texts]

    def rank(
        self,
        query: str,
        documents: Sequence[dict[str, Any]],
        *,
        top_k: int = 100,
        id_key: str = "lesson_id",
        text_key: str = "embedding_text",
    ) -> list[DenseSearchResult]:
        if not query.strip() or not documents or top_k <= 0:
            return []
        query_vector = self.encode_query(query)
        texts = [
            str(document.get(text_key) or document.get("content") or "") for document in documents
        ]
        passage_vectors = self.encode_passages(texts)
        scored = [
            (
                str(document.get(id_key) or document.get("id") or index),
                cosine_similarity(query_vector, vector),
            )
            for index, (document, vector) in enumerate(zip(documents, passage_vectors, strict=True))
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [
            DenseSearchResult(document_id=document_id, score=round(score, 6), rank=rank)
            for rank, (document_id, score) in enumerate(scored[:top_k], start=1)
        ]

    def late_interaction_score(
        self,
        query: str,
        passage: str,
        *,
        max_query_tokens: int = 24,
        max_passage_tokens: int = 160,
    ) -> float:
        """ColBERT-style MaxSim over token vectors.

        This is a late-interaction scoring primitive, not a claim that the
        repository ships the trained ColBERT model.  With the semantic backend
        it embeds tokens through BGE; with the fallback it uses hashed character
        features and remains deterministic.
        """
        query_tokens = list(dict.fromkeys(_tokens(query)))[:max_query_tokens]
        passage_tokens = list(dict.fromkeys(_tokens(passage)))[:max_passage_tokens]
        if not query_tokens or not passage_tokens:
            return 0.0

        if self._model is None:
            maxima = [
                max(
                    _token_similarity(query_token, passage_token)
                    for passage_token in passage_tokens
                )
                for query_token in query_tokens
            ]
            return round(sum(maxima) / len(maxima), 6)

        query_vectors = self.encode_passages(query_tokens)
        passage_vectors = self.encode_passages(passage_tokens)
        try:
            import numpy as np

            maxima = np.matmul(np.asarray(query_vectors), np.asarray(passage_vectors).T).max(axis=1)
        except ImportError:
            maxima = [
                max(
                    cosine_similarity(query_vector, passage_vector)
                    for passage_vector in passage_vectors
                )
                for query_vector in query_vectors
            ]
        return round(sum(maxima) / len(maxima), 6)
