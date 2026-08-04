"""Trading RAG Pipeline — end-to-end capture→retrieve→rerank→gate.

Implements the described pipeline:
    capture 👎 → normalize/quality-gate → store lesson (SQLite FTS5)
      → retrieve: lexical bigram-Jaccard + keyword (pragmatic-hybrid-search)
      → multi-query: up to 3 variants, only when top lexical < 0.6
      → rerank: cross-encoder-reranker (LLM if key present, else heuristic)
      → assemble context → gate the next tool call (deterministic)

Design principles:
- Zero hard dependencies beyond the Python standard library for import.
  Cross-encoder and LLM rerankers are optional and degrade gracefully.
- SQLite FTS5 is the single source of truth for lesson storage.
- Backward-compatible interface: ``TradingRAGPipeline.search()`` returns
  ``(LessonResult, score)`` tuples — same shape as ``LessonsLearnedRAG.search()``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path(os.getenv("TRADING_RAG_DB", ".claude/memory/rag_pipeline.db"))

# Trading-domain synonyms for query expansion (multi-query variant 2)
DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "iron condor": ["ic", "4-leg spread", "short strangle defined risk", "credit spread"],
    "credit spread": ["put spread", "short put", "income strategy", "premium selling"],
    "put spread": ["bear put", "debit spread", "vertical put"],
    "call spread": ["bull call", "debit spread", "vertical call"],
    "csp": ["cash secured put", "naked put", "short put"],
    "vix": ["volatility", "vxv", "volatility index", "vix spike"],
    "delta": ["15 delta", "20 delta", "strike selection", "probability otm"],
    "dte": ["days to expiration", "expiry", "time decay", "7 dte", "0 dte"],
    "position sizing": [
        "position limit",
        "allocation",
        "risk per trade",
        "notional",
        "size",
        "sizing",
        "limit",
    ],
    "stop loss": ["stop-loss", "max loss", "loss limit", "drawdown halt"],
    "section 1256": ["xsp", "spx", "60/40 tax", "index option", "60-40"],
    "1256": ["section 1256", "xsp", "spx", "60/40 tax treatment"],
    "ic": ["iron condor", "neutral credit spread", "income strategy"],
    "sofi": ["sofi", "pdt", "pattern day trader", "margin restriction"],
    "wash sale": ["wash sale", "tax loss harvesting", "30 day", "cost basis"],
    "bogleheads": ["three fund", "buy and hold", "passive investing", "vtsax"],
}

TICKER_REGEX = re.compile(
    r"\b(SPY|XSP|SPX|QQQ|IWM|SOFI|AAPL|MSFT|NVDA|TSLA|VOO|AMZN|META|GOOG|AMD)\b",
    re.IGNORECASE,
)

# Stopwords for tokenization
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "over",
        "your",
        "you",
        "our",
        "are",
        "was",
        "were",
        "why",
        "how",
        "what",
        "when",
        "where",
        "who",
        "which",
        "about",
        "after",
        "before",
        "they",
        "them",
        "their",
        "then",
        "than",
        "but",
        "not",
        "can",
        "could",
        "should",
        "would",
        "will",
        "just",
        "does",
        "did",
        "had",
        "has",
        "have",
        "it",
        "its",
        "be",
        "as",
        "at",
        "by",
        "or",
        "if",
        "in",
        "on",
        "to",
        "of",
        "a",
        "an",
        "is",
    }
)

# Quality gate: a lesson must have a severity and at least one prevention/action section
_REQUIRED_SEVERITY_PATTERN = re.compile(
    r"\*\*severity\*\*:\s*\*?(critical|high|medium|low|p0|p1|p2|p3)\*?",
    re.IGNORECASE,
)

_SECTION_HEADERS = (
    "## prevention",
    "## action",
    "## solution",
    "## fix",
    "## root cause",
    "## what to do",
    "## corrective action",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LessonResult:
    """A single lesson search result with relevance scoring."""

    id: str
    title: str
    severity: str
    snippet: str
    prevention: str
    file: str
    score: float = 0.0


@dataclass
class LessonRecord:
    """A stored lesson record in the SQLite FTS5 table."""

    lesson_id: str
    title: str
    content: str
    severity: str
    prevention: str
    tags: str  # comma-separated
    source: str  # "markdown", "feedback", "anomaly"
    created_at: str


@dataclass
class QueryVariant:
    """A query variant generated by the multi-query engine."""

    text: str
    kind: str  # "original", "synonym_expanded", "keyword_focused"


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BIGRAM_RE = re.compile(r"(\w+\s\w+)")


def tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, extract alphanumerics, filter stopwords and short tokens."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 2 and t not in _STOPWORDS]


def tokenize_bigrams(text: str) -> set[tuple[str, str]]:
    """Extract word bigrams from text as a set of (w1, w2) tuples."""
    tokens = tokenize(text)
    return {tuple(tokens[i : i + 2]) for i in range(len(tokens) - 1)} if len(tokens) >= 2 else set()


def bigram_jaccard_score(query: str, doc_text: str) -> float:
    """Compute Jaccard similarity over word bigram sets.

    Two tokens must be adjacent in *both* the query and the document to count
    as a shared bigram.  Returns a float in [0, 1].
    """
    q_bigrams = tokenize_bigrams(query)
    d_bigrams = tokenize_bigrams(doc_text)
    if not q_bigrams and not d_bigrams:
        return 0.0
    if not q_bigrams or not d_bigrams:
        return 0.0
    intersection = q_bigrams & d_bigrams
    union = q_bigrams | d_bigrams
    return len(intersection) / len(union) if union else 0.0


def normalize_lesson_id(lesson_id: str) -> str:
    """Normalize a lesson ID for comparison: lowercase, strip .md, extract ll-NNN."""
    raw = lesson_id.lower().replace(".md", "")
    match = re.search(r"ll[-_]?(\d+)", raw)
    if match:
        return f"ll-{match.group(1)}"
    return raw


def _stem_tokens(tokens: set[str]) -> set[str]:
    """Apply simple suffix-stripping (Porter-like) to normalize plural/suffixed forms.

    e.g. "sizing" -> "size", "errors" -> "error", "accumulated" -> "accumulat"
    """
    stemmed: set[str] = set()
    for t in tokens:
        s = t.lower()
        # Strip common suffixes
        for suffix in ("ing", "ed", "es", "s"):
            if s.endswith(suffix) and len(s) > len(suffix) + 2:
                s = s[: -len(suffix)]
                break
        # Special: "sizing" -> "size"
        if t.lower().endswith("izing"):
            s = t.lower()[:-3] + "e"  # "sizing" -> "size"
        stemmed.add(s)
    return stemmed


# ---------------------------------------------------------------------------
# SQLite FTS5 storage
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Main lessons table (metadata, not full-text-searchable)
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id   TEXT PRIMARY KEY,
    title       TEXT,
    content     TEXT,
    severity    TEXT DEFAULT 'LOW',
    prevention  TEXT,
    tags        TEXT DEFAULT '',
    source      TEXT DEFAULT 'markdown',
    created_at  TEXT
);

-- FTS5 full-text index (the searchable content)
CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
    content, content_title, lesson_id, tags,
    content='lessons', content_rowid='rowid'
);

-- Trigger to keep FTS index in sync on insert
CREATE TRIGGER IF NOT EXISTS lessons_ai AFTER INSERT ON lessons BEGIN
    INSERT INTO lessons_fts(rowid, content, content_title, lesson_id, tags)
    VALUES (new.rowid, new.content, new.title, new.lesson_id, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS lessons_ad AFTER DELETE ON lessons BEGIN
    INSERT INTO lessons_fts(lessons_fts, rowid, content, content_title, lesson_id, tags)
    VALUES('delete', old.rowid, old.content, old.title, old.lesson_id, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS lessons_au AFTER UPDATE ON lessons BEGIN
    INSERT INTO lessons_fts(lessons_fts, rowid, content, content_title, lesson_id, tags)
    VALUES('delete', old.rowid, old.content, old.title, old.lesson_id, old.tags);
    INSERT INTO lessons_fts(rowid, content, content_title, lesson_id, tags)
    VALUES (new.rowid, new.content, new.title, new.lesson_id, new.tags);
END;
"""


class SQLiteFTS5Store:
    """SQLite-backed FTS5 lesson store with thread-safe access."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode = WAL")
                self._conn.execute("PRAGMA synchronous = NORMAL")
            return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        with self._lock:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        logger.debug("SQLite FTS5 store initialized at %s", self.db_path)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._get_conn()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def put(self, record: LessonRecord) -> None:
        """Insert or replace a lesson record."""
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                """
                INSERT OR REPLACE INTO lessons
                    (lesson_id, title, content, severity, prevention, tags, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.lesson_id,
                    record.title,
                    record.content,
                    record.severity,
                    record.prevention,
                    record.tags,
                    record.source,
                    record.created_at,
                ),
            )
            conn.commit()

    def count(self) -> int:
        conn = self._get_conn()
        with self._lock:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM lessons").fetchone()
            return row["cnt"] if row else 0

    # --- FTS5 query escaping ---
    _FTS_STOPWORDS_REMOVED = False
    _FTS_SPECIAL_CHARS = set("-+*<>(){}[]!\"'")

    @staticmethod
    def _escape_fts_query(query: str) -> str:
        """Escape FTS5 special characters and build a recall-oriented query.

        Uses OR (not implicit AND) so documents matching any query term are
        returned.  This maximizes recall from FTS5; precision is handled by
        the bigram-Jaccard lexical filter and the cross-encoder reranker.
        """
        clean = re.sub(r"[-+*<>{}\[\]!]", " ", query)
        tokens = re.findall(r"[A-Za-z0-9_]+", clean)
        if not tokens:
            return ""
        # Filter out stop words and very short tokens
        meaningful = [t for t in tokens if len(t) >= 2 and t.lower() not in _STOPWORDS]
        if not meaningful:
            meaningful = tokens
        # Quote each term to prevent column-name interpretation (e.g. "RAG")
        quoted = [f'"{t}"' for t in meaningful]
        return " OR ".join(quoted)

    def fts_search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Search the FTS5 index, returning rows with BM25 score + metadata."""
        conn = self._get_conn()
        fts_query = self._escape_fts_query(query)
        if not fts_query:
            return []
        with self._lock:
            rows = conn.execute(
                """
                SELECT
                    l.lesson_id,
                    l.title,
                    l.content,
                    l.severity,
                    l.prevention,
                    l.tags,
                    l.source,
                    l.created_at,
                    bm25(lessons_fts) AS bm25_score
                FROM lessons_fts
                JOIN lessons l ON l.rowid = lessons_fts.rowid
                WHERE lessons_fts MATCH ?
                ORDER BY bm25_score ASC
                LIMIT ?
                """,
                (fts_query, top_k),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all(self) -> list[dict[str, Any]]:
        """Return all lesson records (for indexing into bigram cache)."""
        conn = self._get_conn()
        with self._lock:
            rows = conn.execute(
                """
                SELECT lesson_id, title, content, severity, prevention, tags, source, created_at
                FROM lessons
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_id(self, lesson_id: str) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        with self._lock:
            row = conn.execute("SELECT * FROM lessons WHERE lesson_id = ?", (lesson_id,)).fetchone()
        return dict(row) if row else None

    def upsert_many(self, records: list[LessonRecord]) -> int:
        """Bulk insert/replace multiple lesson records. Returns count inserted."""
        conn = self._get_conn()
        with self._lock:
            conn.executemany(
                """
                INSERT OR REPLACE INTO lessons
                    (lesson_id, title, content, severity, prevention, tags, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.lesson_id,
                        r.title,
                        r.content,
                        r.severity,
                        r.prevention,
                        r.tags,
                        r.source,
                        r.created_at,
                    )
                    for r in records
                ],
            )
            conn.commit()
        return len(records)


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------


def quality_gate(content: str) -> tuple[bool, str]:
    """Normalize and quality-check lesson content before storage.

    Returns (passes, reason).
    A lesson passes if it has:
      - A severity marker (critical/high/medium/low/P0-P3)
      - At least one prevention/action/solution section
      - At least 50 characters of substantive content
    """
    if not content or len(content.strip()) < 50:
        return False, "content too short (< 50 chars)"

    content_lower = content.lower()
    if not _REQUIRED_SEVERITY_PATTERN.search(content):
        return False, "missing severity marker"

    has_section = any(h in content_lower for h in _SECTION_HEADERS)
    if not has_section:
        return False, "missing prevention/action section"

    return True, "ok"


def parse_lesson_markdown(content: str, lesson_id: str | None = None) -> LessonRecord:
    """Parse markdown lesson content into a structured LessonRecord."""
    severity = "LOW"
    sev_match = _REQUIRED_SEVERITY_PATTERN.search(content)
    if sev_match:
        raw_sev = sev_match.group(1).upper()
        if raw_sev.startswith("P"):
            sev_map = {"P0": "CRITICAL", "P1": "HIGH", "P2": "MEDIUM", "P3": "LOW"}
            severity = sev_map.get(raw_sev, "LOW")
        else:
            severity = raw_sev
    severity = severity if severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "LOW"

    # Extract title from first heading
    title_match = re.search(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
    title = title_match.group(1).strip() if title_match else (lesson_id or "Untitled")

    # Extract prevention section
    prevention = ""
    for header in _SECTION_HEADERS:
        pattern = re.escape(header) + r"\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            prevention = match.group(1).strip()[:2000]
            break
    if not prevention:
        prevention = content[:300].strip()

    # Extract tags
    tags_match = re.search(r"##\s*Tags\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if tags_match:
        tags = ", ".join(re.findall(r"`([^`]+)`", tags_match.group(1)))
    else:
        tags = ""

    if lesson_id is None:
        lesson_id = title.replace(" ", "_").lower()[:60] if title else "untitled"
        lesson_id = lesson_id.replace(":", "").replace("/", "_")

    # Normalize severity in the content for downstream consumers
    content = re.sub(
        r"\*\*Severity\*\*:\s*\*?.+?\*?",
        f"**Severity**: {severity}",
        content,
        flags=re.IGNORECASE,
    )

    return LessonRecord(
        lesson_id=lesson_id,
        title=title,
        content=content,
        severity=severity,
        prevention=prevention,
        tags=tags,
        source="markdown",
        created_at=datetime.now(UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Multi-query engine
# ---------------------------------------------------------------------------


def generate_query_variants(query: str, max_variants: int = 3) -> list[QueryVariant]:
    """Generate up to *max_variants* query variants for multi-query retrieval.

    Variants:
      1. original  — the query as-is
      2. synonym_expanded — append domain synonyms
      3. keyword_focused  — strip stop words, keep tickers + key terms
    """
    variants: list[QueryVariant] = [QueryVariant(text=query, kind="original")]

    if max_variants < 2:
        return variants

    # Variant 2: synonym expansion
    q_lower = query.lower()
    added: list[str] = []
    for key, terms in DOMAIN_SYNONYMS.items():
        if key in q_lower:
            for t in terms:
                if t not in q_lower and t not in added:
                    added.append(t)
    if added:
        expanded = f"{query} {' '.join(added[:6])}"
        variants.append(QueryVariant(text=expanded, kind="synonym_expanded"))
    else:
        variants.append(QueryVariant(text=query, kind="synonym_expanded"))

    if max_variants < 3:
        return variants

    # Variant 3: keyword-focused — remove stopwords, keep tickers + remaining tokens
    tickers = TICKER_REGEX.findall(query)
    tokens = tokenize(query)
    keyword_parts = list(dict.fromkeys(tokens))  # dedupe, preserve order
    keyword_str = (
        " ".join(tickers[:3] + keyword_parts[:8]) if tickers else " ".join(keyword_parts[:8])
    )
    variants.append(QueryVariant(text=keyword_str or query, kind="keyword_focused"))

    return variants[:max_variants]


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Cross-encoder weights are immutable and ~80MB; loading them cost ~3-4s on EVERY
# RAGEReranker() construction, and a reranker is built per pipeline. That doubled the
# test suite (640s -> 1277s) and put multiple seconds on the first query of every new
# pipeline. The model is stateless for scoring, so one process-wide instance is correct.
_cross_encoder_cache: dict[str, Any] = {}
_cross_encoder_lock = threading.Lock()


def _load_cross_encoder(model_name: str):
    """Return a process-wide cross-encoder, loading it at most once per model."""
    cached = _cross_encoder_cache.get(model_name)
    if cached is not None:
        return cached
    with _cross_encoder_lock:
        # Re-check inside the lock: two threads can race past the fast path above.
        cached = _cross_encoder_cache.get(model_name)
        if cached is None:
            from sentence_transformers import CrossEncoder

            cached = CrossEncoder(model_name)
            _cross_encoder_cache[model_name] = cached
    return cached


class RAGEReranker:
    """Reranker that uses a cross-encoder when available, LLM when an API key is present,
    and falls back to a domain-keyword heuristic.

    Priority:
      1. ``sentence-transformers`` CrossEncoder  (if installed & model available)
      2. LLM reranker            (if OPENAI_API_KEY or ANTHROPIC_API_KEY set)
      3. Heuristic word-overlap  (always available, zero dependencies)
    """

    # Domain keywords that get a priority boost in the heuristic fallback
    _HIGH_PRIORITY_KEYWORDS: list[str] = [
        "drawdown",
        "circuit breaker",
        "safety buffer",
        "stop loss",
        "position sizing",
        "risk management",
        "section 1256",
        "200-dma",
        "bogleheads",
        "wash sale",
        "pdt",
        "margin",
        "tax",
    ]

    def __init__(self) -> None:
        self._cross_encoder = None
        self._reranker_type = "heuristic"
        self._use_llm = False
        self._llm_client = None
        self._detect_reranker()

    def _detect_reranker(self) -> None:
        """Detect the best available reranker and initialize it."""
        # 1. Try cross-encoder
        try:
            self._cross_encoder = _load_cross_encoder(CROSS_ENCODER_MODEL)
            self._reranker_type = "cross-encoder"
            logger.info("RAGEReranker: using %s", CROSS_ENCODER_MODEL)
            return
        except Exception:
            logger.debug("Cross-encoder unavailable, falling through to LLM/heuristic")

        # 2. Try LLM
        if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            self._use_llm = True
            self._reranker_type = "llm"
            self._init_llm_client()
            logger.info("RAGEReranker: using LLM reranker (key detected)")
            return

        # 3. Heuristic fallback
        self._reranker_type = "heuristic"
        logger.info("RAGEReranker: using heuristic fallback (no cross-encoder/LLM)")

    def _init_llm_client(self) -> None:
        """Initialize LLM client for reranking."""
        if os.getenv("OPENAI_API_KEY"):
            try:
                import openai

                self._llm_client = openai.OpenAI()
                self._llm_provider = "openai"
                return
            except Exception:
                logger.debug("OpenAI client init failed, trying Anthropic")
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                import anthropic

                self._llm_client = anthropic.Anthropic()
                self._llm_provider = "anthropic"
                return
            except Exception:
                logger.debug("Anthropic client init failed, falling back to heuristic")
        self._llm_client = None
        self._use_llm = False
        self._reranker_type = "heuristic"

    @property
    def reranker_type(self) -> str:
        return self._reranker_type

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank candidates. Returns list of dicts with an added ``rerank_score`` key."""
        if not candidates:
            return []

        if self._cross_encoder is not None:
            return self._rerank_cross_encoder(query, candidates, top_n)
        elif self._use_llm and self._llm_client is not None:
            return self._rerank_llm(query, candidates, top_n)
        else:
            return self._rerank_heuristic(query, candidates, top_n)

    def _rerank_cross_encoder(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        """Rerank using cross-encoder, combined with the original hybrid score.

        Uses sigmoid normalization (absolute, not batch-relative) so OOD
        queries get near-zero scores.  Ensembles with the hybrid lexical score:
            final = CE_ALPHA * sigmoid(raw_ce) + (1 - CE_ALPHA) * hybrid_score
        Also adds a title-match boost for domain-specific terms that the CE
        may miss (it's trained on web search, not trading jargon).
        """
        import math

        query_tokens = set(tokenize(query))

        # Include title in the cross-encoder input — titles are strong relevance signals
        pairs = []
        for c in candidates:
            title = c.get("title", "")
            snippet = c.get("content_snippet", c.get("content", ""))[:512]
            pairs.append((query, f"{title} {snippet}"))

        raw_scores = self._cross_encoder.predict(pairs)
        try:
            import numpy as np

            if isinstance(raw_scores, np.ndarray):
                raw_scores = raw_scores.tolist()
        except ImportError:
            pass

        for c, raw_s in zip(candidates, raw_scores, strict=False):
            ce_sig = float(1.0 / (1.0 + math.exp(-float(raw_s))))
            hybrid = float(c.get("score", 0.0))

            # Title-match boost: query tokens appearing in the title get a boost
            title_lower = (c.get("title", "") + " " + str(c.get("id", ""))).lower()
            title_tokens = set(tokenize(title_lower))
            title_overlap = (
                len(query_tokens & title_tokens) / max(len(query_tokens), 1)
                if query_tokens
                else 0.0
            )
            title_boost = title_overlap * 0.12

            c["rerank_score"] = round(
                _CE_ALPHA * ce_sig + (1.0 - _CE_ALPHA) * hybrid + title_boost, 6
            )
            c["_ce_raw"] = float(raw_s)
            c["_ce_sigmoid"] = ce_sig

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_n]

    def _rerank_llm(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        """Use LLM to rerank candidates by relevance to the query."""
        if not candidates:
            return []

        # Limit to a manageable number for LLM reranking
        top_candidates = candidates[: min(10, len(candidates))]
        prompt = self._build_llm_rerank_prompt(query, top_candidates)

        try:
            if self._llm_provider == "openai":
                resp = self._llm_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=512,
                )
                text = resp.choices[0].message.content
            elif self._llm_provider == "anthropic":
                resp = self._llm_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text
            else:
                return self._rerank_heuristic(query, candidates, top_n)

            # Parse ranked lesson IDs from LLM response
            ranked_ids = self._parse_llm_rerank_output(text)
            # Re-order candidates by LLM ranking
            id_to_candidate = {c.get("id"): c for c in top_candidates}
            ranked = [id_to_candidate[lid] for lid in ranked_ids if lid in id_to_candidate]
            # Append any unranked candidates at the end
            unranked = [c for c in top_candidates if c not in ranked]
            result = ranked + unranked
            # Assign scores based on rank position
            for i, c in enumerate(result):
                c["rerank_score"] = 1.0 - (i / max(len(result), 1))
            return result[:top_n]
        except Exception as e:
            logger.warning("LLM reranker failed (%s); falling back to heuristic", e)
            return self._rerank_heuristic(query, candidates, top_n)

    def _build_llm_rerank_prompt(self, query: str, candidates: list[dict]) -> str:
        lines = [
            f"Query: {query}",
            "",
            "Rank the following trading lessons by relevance to the query. Return a JSON array of lesson IDs in order of relevance (most relevant first).",
            "",
        ]
        for i, c in enumerate(candidates):
            snippet = (c.get("content_snippet") or c.get("content", ""))[:200]
            lines.append(f"[{i}] id={c.get('id')} title={c.get('title', '')} snippet={snippet}")
        lines.append("")
        lines.append('Output format: ["id1", "id2", ...]')
        return "\n".join(lines)

    def _parse_llm_rerank_output(self, text: str) -> list[str]:
        """Parse a JSON array of lesson IDs from LLM output."""
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: extract IDs from text
        ids = re.findall(r"[a-zA-Z0-9\-_]+", text)
        return ids

    def _rerank_heuristic(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        """Heuristic reranker: bigram-Jaccard + unigram overlap + keyword TF + domain keywords + severity.

        Uses stemming for token matching, full content (not just snippet), and
        combines multiple lexical signals for robust domain-specific ranking.
        """
        query_lower = query.lower()
        query_tokens = set(tokenize(query))
        stemmed_query = _stem_tokens(query_tokens)

        for c in candidates:
            # Use full content + title for richer matching
            content = c.get("content", c.get("content_snippet", ""))
            title = c.get("title", "")
            lesson_id = str(c.get("id", ""))
            id_text = lesson_id.replace("-", " ").replace("_", " ").lower()
            text = f"{title} {id_text} {content}".lower()

            # Bigram-Jaccard score
            jaccard = bigram_jaccard_score(query, text)

            # Unigram overlap with stemming (handles "sizing" → "size")
            doc_tokens = set(tokenize(text))
            stemmed_doc = _stem_tokens(doc_tokens)
            if stemmed_query and stemmed_doc:
                overlap = len(stemmed_query & stemmed_doc) / max(len(stemmed_query), 1)
                unigram_jaccard = (
                    len(stemmed_query & stemmed_doc) / len(stemmed_query | stemmed_doc)
                    if (stemmed_query | stemmed_doc)
                    else 0.0
                )
            else:
                overlap = 0.0
                unigram_jaccard = 0.0

            # Token frequency in text (how many times query terms appear)
            token_freq = sum(text.count(t) for t in query_tokens if len(t) > 2)
            tf_score = min(token_freq / max(len(query_tokens) * 3, 1), 1.0)

            # Phrase matching bonus
            phrase_bonus = 0.10 if query_lower in text else 0.0

            # Title match boost
            title_tokens = set(tokenize(title.lower()))
            title_match = (
                len(query_tokens & title_tokens) / max(len(query_tokens), 1)
                if query_tokens
                else 0.0
            )

            # Domain priority keyword boost
            priority_boost = 0.0
            for kw in self._HIGH_PRIORITY_KEYWORDS:
                if kw in text:
                    priority_boost += 0.08

            # Severity weight
            sev = (c.get("severity") or "").upper()
            sev_weight = {"CRITICAL": 1.35, "HIGH": 1.2, "MEDIUM": 1.0, "LOW": 0.9}.get(sev, 1.0)

            orig_score = float(c.get("score", 0.0) or 0.0)
            rerank_score = (
                (orig_score * 0.35)
                + (jaccard * 0.15)
                + (overlap * 0.10)
                + (unigram_jaccard * 0.10)
                + (tf_score * 0.10)
                + phrase_bonus
                + (title_match * 0.10)
                + (priority_boost * sev_weight)
            )
            c["rerank_score"] = round(rerank_score, 6)

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_n]


# ---------------------------------------------------------------------------
# Pragmatic hybrid search (bigram-Jaccard + keyword)
# ---------------------------------------------------------------------------


@dataclass
class HybridHit:
    """A single hybrid search result."""

    id: str
    title: str
    severity: str
    snippet: str
    prevention: str
    file: str
    lexical_score: float  # bigram-Jaccard
    keyword_score: float  # SQLite BM25 (normalized)
    combined_score: float
    raw: dict[str, Any] = field(default_factory=dict)


def pragmatic_hybrid_search(
    query: str,
    lessons: list[dict[str, Any]],
    top_k: int = 10,
    keyword_weight: float = 0.35,
    lexical_weight: float = 0.30,
    unigram_weight: float = 0.25,
) -> list[HybridHit]:
    """Combine bigram-Jaccard lexical similarity with BM25 keyword search.

    This is the *pragmatic* hybrid:
    - Bigram-Jaccard: set-based similarity over word bigrams (captures multi-word phrases)
    - BM25 keyword: term-frequency * IDF scoring (from SQLite FTS5)
    - Unigram overlap: term-level Jaccard over query tokens (handles short queries
      where bigrams rarely match because query terms are spread across paragraphs)
    - Title boost: tokens in the title get a 0.15 multiplier
    - Phrase boost: if the exact query appears in the text, +0.15
    - Token floor: if doc contains ANY query token, minimum combined score = 0.10

    Scores are normalized to [0, 1] and combined with configurable weights.
    """
    if not lessons:
        return []

    query_bigrams = tokenize_bigrams(query)
    query_tokens = set(tokenize(query))

    hits: list[HybridHit] = []

    # Max BM25 for normalization
    max_bm25 = max(abs(item.get("bm25_score", 0.0)) for item in lessons) if lessons else 1.0
    if max_bm25 < 1e-9:
        max_bm25 = 1.0

    query_lower = query.lower()
    title_boost_value = 0.15

    for lesson in lessons:
        content = lesson.get("content", "")
        title = lesson.get("title", "")
        lesson_id = str(lesson.get("lesson_id", lesson.get("id", "")))
        # Include ID in search text — IDs contain title keywords (e.g. LL-290_Position_Accumulation_Bug)
        id_text = lesson_id.replace("-", " ").replace("_", " ").lower()
        full_text = f"{title} {id_text} {content}"
        text_lower = full_text.lower()
        title_lower = f"{title} {id_text}".lower()

        # --- Lexical: bigram-Jaccard ---
        doc_bigrams = tokenize_bigrams(text_lower)
        if query_bigrams and doc_bigrams:
            intersection = len(query_bigrams & doc_bigrams)
            union = len(query_bigrams | doc_bigrams)
            lexical = intersection / union if union else 0.0
        else:
            lexical = 0.0

        # --- Unigram overlap (term-level Jaccard) with prefix matching ---
        doc_tokens = set(tokenize(text_lower))
        # Prefix matching: "sizing" matches "size", "error" matches "errors"
        stemmed_doc = set(_stem_tokens(doc_tokens))
        stemmed_query = set(_stem_tokens(query_tokens))
        if stemmed_query and stemmed_doc:
            unigram = len(stemmed_query & stemmed_doc) / len(stemmed_query | stemmed_doc)
        else:
            unigram = (
                len(query_tokens & doc_tokens) / len(query_tokens | doc_tokens)
                if (query_tokens and doc_tokens)
                else 0.0
            )

        # --- Phrase matching bonus ---
        phrase_bonus = 0.15 if query_lower and query_lower in text_lower else 0.0

        # --- Title boost ---
        title_tokens = set(tokenize(title_lower))
        title_match = (
            len(query_tokens & title_tokens) / max(len(query_tokens), 1) if query_tokens else 0.0
        )

        # --- Keyword: BM25 (from SQLite FTS5, or TF fallback) ---
        raw_bm25 = abs(float(lesson.get("bm25_score", 0.0)))
        keyword = raw_bm25 / max_bm25 if raw_bm25 > 0 else 0.0

        # TF fallback if BM25 is 0
        if keyword == 0.0 and query_tokens:
            term_hits = sum(1 for t in query_tokens if t in text_lower)
            keyword = min(term_hits / max(len(query_tokens), 1), 1.0)

        # --- Token floor: if doc contains ANY query token, ensure minimum score ---
        token_floor = 0.0
        if stemmed_query and stemmed_doc and (stemmed_query & stemmed_doc):
            token_floor = 0.10

        # --- Combined ---
        combined = (
            (lexical_weight * lexical)
            + (keyword_weight * keyword)
            + (unigram_weight * unigram)
            + phrase_bonus
            + (title_match * title_boost_value)
            + token_floor
        )

        snippet = (content[:500] if len(content) > 500 else content) if content else title

        prevention = lesson.get("prevention", "")
        if not prevention:
            prevention = lesson.get("content", "")[:500]

        hits.append(
            HybridHit(
                id=lesson_id,
                title=title,
                severity=(lesson.get("severity") or "LOW").upper(),
                snippet=snippet,
                prevention=prevention,
                file=lesson.get("file", lesson.get("source", "")),
                lexical_score=round(lexical, 6),
                keyword_score=round(keyword, 6),
                combined_score=round(combined, 6),
                raw=lesson,
            )
        )

    hits.sort(key=lambda h: h.combined_score, reverse=True)
    return hits[:top_k]


# ---------------------------------------------------------------------------
# Deterministic gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateDecision:
    """Deterministic gate decision for a tool call."""

    approved: bool
    severity: str  # "APPROVED", "WARN", "BLOCK"
    reason: str
    blocking_lessons: list[str]
    warning_lessons: list[str]
    top_score: float


# Default thresholds — deterministic, no LLM involved
_BLOCK_THRESHOLD_CRITICAL: float = 0.50
_BLOCK_THRESHOLD_HIGH: float = 0.70
_WARN_THRESHOLD: float = 0.15

# Minimum rerank score to be returned as a result — filters out-of-domain noise
_MIN_RESULT_SCORE: float = 0.05

# Cross-encoder ensemble weight: 0.15 = 15% semantic + 85% hybrid lexical
_CE_ALPHA: float = 0.15

# Cross-encoder sigmoid threshold for OOD detection: if max CE sigmoid below this,
# the query is considered out-of-domain and returns empty results
_CE_OOD_THRESHOLD: float = 0.10

# Multi-query expansion threshold: if top combined score is below this, expand
# the query with synonyms and keyword-focused variants for better recall
_MULTI_QUERY_THRESHOLD: float = 0.55


def gate_decision(top_lessons: list[tuple[LessonResult, float]]) -> GateDecision:
    """Deterministically gate a tool call based on retrieved lesson scores and severity.

    Rules (deterministic, threshold-based):
      - CRITICAL + score > 0.50 → BLOCK
      - HIGH    + score > 0.70 → BLOCK
      - CRITICAL/HIGH + score > 0.15 → WARN (soft)
      - Otherwise → APPROVED
    """
    if not top_lessons:
        return GateDecision(
            approved=True,
            severity="APPROVED",
            reason="No relevant lessons found.",
            blocking_lessons=[],
            warning_lessons=[],
            top_score=0.0,
        )

    blocking: list[str] = []
    warnings: list[str] = []
    max_score = 0.0

    for lesson, score in top_lessons:
        max_score = max(max_score, score)
        sev = lesson.severity.upper()

        is_blocking = (sev == "CRITICAL" and score > _BLOCK_THRESHOLD_CRITICAL) or (
            sev == "HIGH" and score > _BLOCK_THRESHOLD_HIGH
        )
        if is_blocking:
            blocking.append(f"[{sev}] {lesson.title} (score={score:.2f})")
        elif sev in ("CRITICAL", "HIGH") and score > _WARN_THRESHOLD:
            warnings.append(f"[{sev}] {lesson.title} (score={score:.2f})")

    if blocking:
        return GateDecision(
            approved=False,
            severity="BLOCK",
            reason=f"Blocked by {len(blocking)} critical/high lessons: {'; '.join(blocking)}",
            blocking_lessons=blocking,
            warning_lessons=warnings,
            top_score=max_score,
        )

    if warnings:
        return GateDecision(
            approved=True,
            severity="WARN",
            reason=f"Warnings: {'; '.join(warnings)}",
            blocking_lessons=[],
            warning_lessons=warnings,
            top_score=max_score,
        )

    return GateDecision(
        approved=True,
        severity="APPROVED",
        reason=f"All {len(top_lessons)} retrieved lessons below warning threshold.",
        blocking_lessons=[],
        warning_lessons=[],
        top_score=max_score,
    )


# ---------------------------------------------------------------------------
# The full pipeline
# ---------------------------------------------------------------------------


class TradingRAGPipeline:
    """End-to-end RAG pipeline for the trading system.

    Usage:
        pipeline = TradingRAGPipeline()
        pipeline.index_from_markdown_dir("rag_knowledge/lessons_learned")
        results, decision = pipeline.query("iron condor stop loss failure")
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        lessons_dir: str | Path | None = None,
    ):
        self.store = SQLiteFTS5Store(db_path=db_path or DEFAULT_DB_PATH)
        self.lessons_dir = Path(lessons_dir) if lessons_dir else None
        self._reranker = RAGEReranker()
        self._lessons_cache: list[dict[str, Any]] = []
        self._cache_loaded = False

    # -- Stage 1: Capture --> normalize --> quality-gate --> store (SQLite FTS5) --

    def capture_feedback(
        self,
        feedback_text: str,
        *,
        lesson_id: str | None = None,
        source: str = "feedback",
    ) -> tuple[bool, str]:
        """Capture 👎 feedback, normalize, quality-gate, and store in SQLite FTS5.

        Returns (stored, reason).
        """
        # Normalize: strip whitespace, collapse newlines
        normalized = re.sub(r"\s+", " ", feedback_text).strip()

        passes, reason = quality_gate(normalized)
        if not passes:
            return False, reason

        record = parse_lesson_markdown(normalized, lesson_id=lesson_id)
        record = LessonRecord(
            lesson_id=record.lesson_id,
            title=record.title,
            content=record.content,
            severity=record.severity,
            prevention=record.prevention,
            tags=record.tags,
            source=source,
            created_at=datetime.now(UTC).isoformat(),
        )
        self.store.put(record)
        self._cache_loaded = False  # invalidate cache
        return True, f"Stored lesson '{record.lesson_id}'"

    def add_lesson(self, lesson_id: str, content: str, *, source: str = "manual") -> bool:
        """Convenience alias: add a lesson with quality gate."""
        normalized = re.sub(r"\s+", " ", content).strip()
        passes, reason = quality_gate(normalized)
        if not passes:
            logger.warning("Lesson '%s' failed quality gate: %s", lesson_id, reason)
            return False
        record = parse_lesson_markdown(normalized, lesson_id=lesson_id)
        record = LessonRecord(
            lesson_id=lesson_id,
            title=record.title,
            content=record.content,
            severity=record.severity,
            prevention=record.prevention,
            tags=record.tags,
            source=source,
            created_at=datetime.now(UTC).isoformat(),
        )
        self.store.put(record)
        self._cache_loaded = False
        return True

    # -- Indexing --

    def _ensure_loaded(self) -> None:
        if self._cache_loaded:
            return
        self._lessons_cache = self.store.get_all()
        self._cache_loaded = True
        if not self._lessons_cache and self.lessons_dir:
            self.index_from_markdown_dir(self.lessons_dir)

    def index_from_markdown_dir(self, lessons_dir: str | Path) -> int:
        """Load all markdown lessons from a directory into SQLite FTS5."""
        path = Path(lessons_dir)
        if not path.exists():
            logger.warning("Lessons directory not found: %s", path)
            return 0

        records: list[LessonRecord] = []
        for f in sorted(path.glob("*.md")):
            content = f.read_text(encoding="utf-8", errors="ignore")
            record = parse_lesson_markdown(content, lesson_id=f.stem)
            record = LessonRecord(
                lesson_id=record.lesson_id,
                title=record.title,
                content=record.content,
                severity=record.severity,
                prevention=record.prevention,
                tags=record.tags,
                source=record.source,
                created_at=record.created_at,
            )
            records.append(record)

        count = self.store.upsert_many(records)
        self._lessons_cache = self.store.get_all()
        self._cache_loaded = True
        logger.info("Indexed %d lessons from %s into SQLite FTS5", count, path)
        return count

    @property
    def lesson_count(self) -> int:
        self._ensure_loaded()
        return len(self._lessons_cache)

    # -- Stages 2-5: Query pipeline --

    def query(
        self,
        query: str,
        top_k: int = 5,
        *,
        severity_filter: str | None = None,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute the full retrieval pipeline and return ranked results.

        Pipeline:
          1. FTS5 keyword search (BM25) — the candidate generator
          2. Pragmatic hybrid: bigram-Jaccard (45%) + BM25 (55%) on FTS5 results
          3. If top lexical < 0.6, multi-query expansion (up to 3 variants)
          4. Rerank with cross-encoder / LLM / heuristic
          5. Dual-threshold OOD filter: reject if max CE sigmoid < CE_OOD_THRESHOLD
          6. Return top-k results as dicts with scores
        """
        self._ensure_loaded()

        # --- Stage 1+2: FTS5 search → pragmatic hybrid (bigram-Jaccard + BM25) ---
        # Get FTS5 results with proper BM25 scores for this query.
        # Use a large candidate pool (200) — FTS5 is the candidate generator;
        # bigram-Jaccard + cross-encoder handle precision.
        fts_results = self.store.fts_search(query, top_k=200)
        if severity_filter:
            fts_results = [
                item
                for item in fts_results
                if item.get("severity", "").upper() == severity_filter.upper()
            ]

        # Pragmatic hybrid search: bigram-Jaccard on top of FTS5 BM25 results
        hits = pragmatic_hybrid_search(query, fts_results, top_k=top_k * 8)

        # --- Stage 3: Multi-query expansion ---
        # Trigger when the top combined score is below threshold — this means
        # the initial candidate pool lacks strong matches, and query expansion
        # (synonyms, keyword focus) can help surface the right lessons.
        top_combined = hits[0].combined_score if hits else 0.0
        if top_combined < _MULTI_QUERY_THRESHOLD:
            variants = generate_query_variants(query, max_variants=3)
            for variant in variants:
                v_fts = self.store.fts_search(variant.text, top_k=100)
                if severity_filter:
                    v_fts = [
                        item
                        for item in v_fts
                        if item.get("severity", "").upper() == severity_filter.upper()
                    ]
                v_hits = pragmatic_hybrid_search(variant.text, v_fts, top_k=top_k * 2)
                # Merge by lesson_id, keeping highest combined_score
                existing_ids = {h.id for h in hits}
                for vh in v_hits:
                    if vh.id not in existing_ids:
                        hits.append(vh)
                        existing_ids.add(vh.id)
                    else:
                        # Upgrade if new result has higher combined score
                        for i, existing in enumerate(hits):
                            if existing.id == vh.id and vh.combined_score > existing.combined_score:
                                hits[i] = vh
                                break
                if len(hits) >= top_k * 20:
                    break
            hits.sort(key=lambda h: h.combined_score, reverse=True)

        if not hits:
            return []

        # --- Stage 4+5: OOD detection + rerank ---
        if rerank:
            candidates = [
                {
                    "id": h.id,
                    "title": h.title,
                    "severity": h.severity,
                    "content_snippet": h.snippet,
                    "content": h.raw.get("content", h.snippet),
                    "prevention": h.prevention,
                    "file": h.file,
                    "score": h.combined_score,
                    "lexical_score": h.lexical_score,
                    "keyword_score": h.keyword_score,
                }
                for h in hits[:200]  # rerank top 200
            ]

            # --- Stage 5: OOD detection via cross-encoder sigmoid ---
            # Run CE on candidates to check domain relevance; sigmoid is absolute
            # (not batch-relative), so OOD queries get near-zero scores
            if self._reranker._cross_encoder is not None and candidates:
                ce_candidates = [dict(c) for c in candidates]
                ce_pass = self._reranker._rerank_cross_encoder(
                    query, ce_candidates, top_n=len(ce_candidates)
                )
                max_ce_sig = max((float(r.get("_ce_sigmoid", 0.0)) for r in ce_pass), default=0.0)
                if max_ce_sig < _CE_OOD_THRESHOLD:
                    return []  # Out-of-domain — all CE scores too low

            # --- Stage 4: Rerank with cross-encoder (ensemble with hybrid) ---
            reranked = self._reranker.rerank(query, candidates, top_n=top_k * 8)

            # Filter by minimum rerank score
            reranked = [
                r for r in reranked if float(r.get("rerank_score", 0.0)) >= _MIN_RESULT_SCORE
            ]

            results = []
            for c in reranked:
                results.append(
                    {
                        "id": c["id"],
                        "title": c["title"],
                        "severity": c["severity"].upper(),
                        "snippet": c.get("content_snippet", c.get("content", ""))[:500],
                        "content": c.get("content", ""),
                        "prevention": c.get("prevention", ""),
                        "file": c.get("file", ""),
                        "score": c.get("rerank_score", c.get("score", 0.0)),
                        "lexical_score": next(
                            (h.lexical_score for h in hits if h.id == c["id"]), 0.0
                        ),
                        "keyword_score": next(
                            (h.keyword_score for h in hits if h.id == c["id"]), 0.0
                        ),
                        "reranker_type": self._reranker.reranker_type,
                    }
                )
            return results[:top_k]

        # --- No rerank — return hybrid results with OOD filter ---
        results = []
        for h in hits[:top_k]:
            if h.combined_score >= _MIN_RESULT_SCORE:
                results.append(
                    {
                        "id": h.id,
                        "title": h.title,
                        "severity": h.severity.upper(),
                        "snippet": h.snippet,
                        "content": h.raw.get("content", h.snippet),
                        "prevention": h.prevention,
                        "file": h.file,
                        "score": h.combined_score,
                        "lexical_score": h.lexical_score,
                        "keyword_score": h.keyword_score,
                        "reranker_type": self._reranker.reranker_type,
                    }
                )
        return results

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        severity_filter: str | None = None,
    ) -> list[tuple[LessonResult, float]]:
        """Search interface compatible with gates.py and main.py.

        Returns list of (LessonResult, score) tuples.
        """
        raw = self.query(query, top_k=top_k, severity_filter=severity_filter)
        results: list[tuple[LessonResult, float]] = []
        for item in raw:
            lesson = LessonResult(
                id=item["id"],
                title=item.get("title", item["id"]),
                severity=item.get("severity", "LOW"),
                snippet=item.get("snippet", ""),
                prevention=item.get("prevention", ""),
                file=item.get("file", ""),
                score=item["score"],
            )
            results.append((lesson, item["score"]))
        return results

    def retrieve_and_gate(
        self,
        query: str,
        top_k: int = 5,
        *,
        severity_filter: str | None = None,
    ) -> tuple[list[tuple[LessonResult, float]], GateDecision, str]:
        """Full pipeline: retrieve → assemble context → deterministic gate.

        Returns (results, gate_decision, context_string).
        """
        results = self.search(query, top_k=top_k, severity_filter=severity_filter)
        decision = gate_decision(results)

        # Assemble context
        context_parts = []
        for i, (lesson, score) in enumerate(results, 1):
            context_parts.append(
                f"[{i}] ({lesson.severity}) {lesson.title} | score={score:.3f} | id={lesson.id}"
            )
            context_parts.append(lesson.snippet[:300])
            context_parts.append("")
        context = "\n".join(context_parts) if context_parts else "No relevant lessons found."

        return results, decision, context

    def get_critical_lessons(self) -> list[dict[str, Any]]:
        """Return all CRITICAL severity lessons."""
        self._ensure_loaded()
        return [
            item for item in self._lessons_cache if item.get("severity", "").upper() == "CRITICAL"
        ]

    def close(self) -> None:
        self.store.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_default_pipeline: Optional[TradingRAGPipeline] = None
_default_lock = threading.Lock()


def get_trading_rag_pipeline(
    db_path: str | Path | None = None,
    lessons_dir: str | Path | None = None,
    refresh: bool = False,
) -> TradingRAGPipeline:
    """Get or create the singleton TradingRAGPipeline instance."""
    global _default_pipeline
    if _default_pipeline is None or refresh:
        with _default_lock:
            if _default_pipeline is None or refresh:
                db = db_path or DEFAULT_DB_PATH
                lessons = lessons_dir or (
                    Path(__file__).parent.parent.parent / "rag_knowledge" / "lessons_learned"
                )
                _default_pipeline = TradingRAGPipeline(db_path=db, lessons_dir=lessons)
    return _default_pipeline
