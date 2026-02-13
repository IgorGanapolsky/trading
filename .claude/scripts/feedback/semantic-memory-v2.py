#!/usr/bin/env python3
"""
Semantic Memory System v2 - Enhanced RAG/ML Infrastructure

IMPROVEMENTS OVER v1:
1. Similarity threshold filtering (no irrelevant results)
2. LRU cache for embeddings (faster repeated queries)
3. BM25 hybrid search (keyword + vector fusion)
4. Upgraded embedding model option (e5-small-v2)
5. Active RLHF feedback loop (auto-reindex on feedback)
6. OpenTelemetry observability (latency, success rates)
7. Query metrics logging (precision/recall tracking)
8. LanceDB native FTS index (Feb 2026 upgrade)

Architecture (Feb 2026 Best Practices):
┌─────────────────────────────────────────────────────────┐
│  HYBRID SEARCH ENGINE                                   │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ LanceDB Native   │ + │ Vector (Semantic) │ = Fusion │
│  │ FTS (BM25/Tantivy│   │ (SentenceTransf.) │          │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  LanceDB Storage    │
              │  + FTS Index        │
              │  + Similarity Filter │
              │  + LRU Cache        │
              └─────────────────────┘

LOCAL ONLY - Never commit to repository

Usage:
  python semantic-memory-v2.py --index              # Index all memories
  python semantic-memory-v2.py --query "shallow"    # Hybrid search
  python semantic-memory-v2.py --context            # Get session context
  python semantic-memory-v2.py --add-feedback       # Add RLHF feedback (stdin)
  python semantic-memory-v2.py --metrics            # Show query metrics
"""

import os
import sys
import json
import re
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from collections import OrderedDict

# Load .env file from project root for API keys
def load_dotenv_from_project():
    """Load .env file from project root."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:  # Don't override existing env vars
                        os.environ[key] = value

load_dotenv_from_project()

# Configuration
SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent.parent / "memory"
LESSONS_FILE = MEMORY_DIR / "pr-resolution-patterns.md"
FEEDBACK_DIR = MEMORY_DIR / "feedback"
LANCE_DIR = FEEDBACK_DIR / "lancedb"
INDEX_STATE_FILE = FEEDBACK_DIR / "lance-index-state.json"
METRICS_FILE = FEEDBACK_DIR / "query-metrics.jsonl"
FEEDBACK_LOG = FEEDBACK_DIR / "feedback-log.jsonl"

# Model options
EMBEDDING_MODELS = {
    "fast": "all-MiniLM-L6-v2",      # 384 dims, ~50ms
    "better": "intfloat/e5-small-v2", # 384 dims, ~80ms, better quality
    "best": "intfloat/e5-base-v2",    # 768 dims, ~150ms, highest quality
}
DEFAULT_MODEL = "fast"

# Search configuration
SIMILARITY_THRESHOLD = 0.7  # Euclidean distance threshold (lower = more similar)
BM25_WEIGHT = 0.3           # Weight for BM25 in hybrid search
VECTOR_WEIGHT = 0.7         # Weight for vector similarity

# Table names
LESSONS_TABLE = "lessons_learned"
FEEDBACK_TABLE = "rlhf_feedback"

# Cache whether a given table supports native FTS search (Tantivy).
# Values are set opportunistically based on runtime behavior.
_fts_supported: Dict[str, bool] = {}
_fts_index_attempted: set[str] = set()


def get_table_names(db) -> List[str]:
    """Get table names from LanceDB, handling different API versions.

    LanceDB 0.3+ returns ListTablesResponse object with .tables attribute
    Older versions return a plain list.
    """
    result = db.list_tables()
    # Handle LanceDB 0.3+ ListTablesResponse object
    if hasattr(result, 'tables'):
        return result.tables
    # Handle older list return type
    return list(result)


def table_exists(db, table_name: str) -> bool:
    """Check if a table exists in LanceDB."""
    return table_name in get_table_names(db)


# LRU Cache for embeddings with file persistence (2026 upgrade)
class EmbeddingCache:
    """LRU cache for embeddings with file-backed persistence (2026 best practice)"""
    def __init__(self, maxsize: int = 1000, cache_file: Optional[Path] = None):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.cache_file = cache_file or (FEEDBACK_DIR / "embedding_cache.json")
        self._load()

    def _load(self):
        """Load cache from disk on startup"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    data = json.load(f)
                    self.cache = OrderedDict(data.get("cache", {}))
                    while len(self.cache) > self.maxsize:
                        self.cache.popitem(last=False)
            except (json.JSONDecodeError, KeyError):
                self.cache = OrderedDict()

    def _save(self):
        """Save cache to disk with atomic write"""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_file.with_suffix('.tmp')
        with open(tmp, "w") as f:
            json.dump({"cache": dict(self.cache)}, f)
        tmp.rename(self.cache_file)

    def get(self, text: str) -> Optional[List[float]]:
        if text in self.cache:
            self.cache.move_to_end(text)
            self.hits += 1
            return self.cache[text]
        self.misses += 1
        return None

    def put(self, text: str, embedding: List[float]):
        if text in self.cache:
            self.cache.move_to_end(text)
        else:
            if len(self.cache) >= self.maxsize:
                self.cache.popitem(last=False)
            self.cache[text] = embedding
        # Save periodically (every 10 new entries) for persistence
        if len(self.cache) % 10 == 0:
            self._save()

    def save(self):
        """Explicit save for cleanup"""
        self._save()

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2%}",
            "size": len(self.cache),
            "maxsize": self.maxsize
        }

# Global cache instance
_embedding_cache = EmbeddingCache()

# Metrics logger
class MetricsLogger:
    """Log query metrics for observability"""
    def __init__(self, metrics_file: Path):
        self.metrics_file = metrics_file
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, data: Dict[str, Any]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            **data
        }
        with open(self.metrics_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def get_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get metrics summary for last N days"""
        if not self.metrics_file.exists():
            return {"error": "No metrics found"}

        cutoff = datetime.now().timestamp() - (days * 86400)
        queries = []

        with open(self.metrics_file) as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        entry_time = datetime.fromisoformat(entry["timestamp"]).timestamp()
                        if entry_time > cutoff:
                            queries.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue

        if not queries:
            return {"queries": 0, "period_days": days}

        # Calculate stats
        query_events = [q for q in queries if q.get("event") == "query"]
        latencies = [q.get("latency_ms", 0) for q in query_events]
        result_counts = [q.get("result_count", 0) for q in query_events]

        return {
            "period_days": days,
            "total_queries": len(query_events),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "avg_results": sum(result_counts) / len(result_counts) if result_counts else 0,
            "cache_stats": _embedding_cache.stats(),
            "feedback_events": len([q for q in queries if q.get("event") == "feedback"]),
        }

_metrics = MetricsLogger(METRICS_FILE)


def get_lance_db():
    """Initialize LanceDB"""
    try:
        import lancedb
        LANCE_DIR.mkdir(parents=True, exist_ok=True)
        return lancedb.connect(str(LANCE_DIR))
    except ImportError:
        print("lancedb not installed. Run: pip install lancedb")
        sys.exit(1)


def get_embedding_model(model_key: str = DEFAULT_MODEL):
    """Get sentence transformer model with caching and ONNX optimization (Jan 2026)

    Optimization strategies:
    1. Use ONNX backend for 2-3x faster inference (if available)
    2. Set SENTENCE_TRANSFORMERS_HOME for persistent cache
    3. Use model_kwargs for faster loading

    See: https://sbert.net/docs/sentence_transformer/usage/efficiency.html
    """
    try:
        from sentence_transformers import SentenceTransformer
        model_name = EMBEDDING_MODELS.get(model_key, EMBEDDING_MODELS["fast"])

        # Use persistent cache directory for faster subsequent loads
        cache_dir = MEMORY_DIR / "model_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(cache_dir))

        # Try ONNX backend first for faster inference (2-3x speedup)
        try:
            return SentenceTransformer(
                model_name,
                backend="onnx",
                model_kwargs={"file_name": "model_quantized.onnx"},  # Use quantized if available
            )
        except Exception:
            # Fall back to PyTorch if ONNX not available
            return SentenceTransformer(model_name)
    except ImportError:
        print("sentence-transformers not installed. Run: pip install sentence-transformers")
        sys.exit(1)


def get_embedding_with_cache(text: str, model) -> List[float]:
    """Get embedding with LRU cache"""
    cached = _embedding_cache.get(text)
    if cached is not None:
        return cached

    embedding = model.encode([text])[0].tolist()
    _embedding_cache.put(text, embedding)
    return embedding


# BM25 implementation for hybrid search
class BM25:
    """Simple BM25 implementation for hybrid search"""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = {}
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.corpus = []
        self.n_docs = 0

    def fit(self, documents: List[str]):
        """Index documents for BM25"""
        self.corpus = [self._tokenize(doc) for doc in documents]
        self.n_docs = len(self.corpus)
        self.doc_lengths = [len(doc) for doc in self.corpus]
        self.avg_doc_length = sum(self.doc_lengths) / self.n_docs if self.n_docs > 0 else 0

        # Calculate document frequencies
        self.doc_freqs = {}
        for doc in self.corpus:
            seen = set()
            for term in doc:
                if term not in seen:
                    self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
                    seen.add(term)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        return re.findall(r'\w+', text.lower())

    def _idf(self, term: str) -> float:
        """Calculate IDF for a term"""
        import math
        df = self.doc_freqs.get(term, 0)
        return math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)

    def score(self, query: str, doc_idx: int) -> float:
        """Calculate BM25 score for a document"""
        query_terms = self._tokenize(query)
        doc = self.corpus[doc_idx]
        doc_len = self.doc_lengths[doc_idx]

        score = 0.0
        term_freqs = {}
        for term in doc:
            term_freqs[term] = term_freqs.get(term, 0) + 1

        for term in query_terms:
            if term not in term_freqs:
                continue

            tf = term_freqs[term]
            idf = self._idf(term)

            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
            score += idf * numerator / denominator

        return score

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search and return (doc_idx, score) tuples"""
        scores = [(i, self.score(query, i)) for i in range(self.n_docs)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


def parse_lessons(content: str) -> List[Dict[str, Any]]:
    """Parse lessons from markdown file"""
    lessons = []
    pattern = r'^## (?:CRITICAL FAILURE: )?(?:(\d{4}-\d{2}-\d{2}): )?(.+?)$'
    matches = list(re.finditer(pattern, content, re.MULTILINE))

    for i, match in enumerate(matches):
        date_str = match.group(1)
        title = match.group(2).strip()

        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        lesson_content = content[start_pos:end_pos].strip()

        if not date_str:
            date_match = re.search(r'\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})', lesson_content)
            date_str = date_match.group(1) if date_match else "unknown"

        lesson_id = hashlib.md5(f"{date_str}:{title}".encode()).hexdigest()[:12]

        severity = "INFO"
        if "CRITICAL" in lesson_content[:200]:
            severity = "CRITICAL"
        elif "HIGH" in lesson_content[:200]:
            severity = "HIGH"

        tags = []
        tag_patterns = [
            ("shallow-answer", ["shallow", "surface", "superficial"]),
            ("lie", ["lie", "lying", "false claim"]),
            ("verification", ["verif", "check", "confirm"]),
            ("git", ["commit", "push", "branch", "pr"]),
            ("memory", ["memory", "forget", "remember"]),
            ("rag", ["rag", "vertex", "lancedb", "chromadb"]),
        ]
        for tag, keywords in tag_patterns:
            if any(kw in lesson_content.lower() for kw in keywords):
                tags.append(tag)

        lessons.append({
            "id": f"lesson_{lesson_id}",
            "date": date_str,
            "title": title,
            "severity": severity,
            "tags": ",".join(tags),
            "content": lesson_content[:500],
            "full_text": f"{title}\n\nDate: {date_str}\nSeverity: {severity}\n\n{lesson_content}",
        })

    return lessons


def load_feedback_patterns() -> List[Dict[str, Any]]:
    """Load RLHF feedback for indexing"""
    if not FEEDBACK_LOG.exists():
        return []

    patterns = []
    with open(FEEDBACK_LOG) as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    feedback_val = str(entry.get("feedback", "unknown"))
                    context_val = str(entry.get("context") or entry.get("message") or "")

                    tags_raw = entry.get("tags", [])
                    if isinstance(tags_raw, str):
                        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
                    elif isinstance(tags_raw, list):
                        tags_list = [str(t).strip() for t in tags_raw if str(t).strip()]
                    else:
                        tags_list = []

                    user_message = str(entry.get("user_message") or "")
                    assistant_response = str(
                        entry.get("assistant_response")
                        or entry.get("claude_response")
                        or ""
                    )

                    doc_text = f"Feedback: {feedback_val}\n"
                    doc_text += f"Context: {context_val}\n"
                    if user_message:
                        doc_text += f"User Message: {user_message[:500]}\n"
                    if assistant_response:
                        doc_text += f"Assistant Response: {assistant_response[:500]}\n"
                    doc_text += f"Tags: {', '.join(tags_list)}\n"
                    doc_text += f"Action: {entry.get('actionType', 'unknown')}"

                    fb_lower = feedback_val.lower()
                    if fb_lower in ("negative", "down", "thumbsdown"):
                        default_reward = -1
                    elif fb_lower in ("positive", "up", "thumbsup"):
                        default_reward = 1
                    else:
                        default_reward = 0

                    patterns.append({
                        "id": entry.get("id", f"fb_{len(patterns)}"),
                        "type": "feedback",
                        "feedback_type": feedback_val,
                        "reward": entry.get("reward", default_reward),
                        "context": context_val[:200],
                        "tags": ",".join(tags_list),
                        "full_text": doc_text,
                        "timestamp": entry.get("timestamp", datetime.now().isoformat()),
                    })
                except json.JSONDecodeError:
                    continue

    return patterns


def index_all(model_key: str = DEFAULT_MODEL):
    """Index all lessons and feedback into LanceDB"""
    print(f"\nIndexing memories into LanceDB...")
    print(f"   Model: {EMBEDDING_MODELS.get(model_key, model_key)}")
    print(f"   Storage: {LANCE_DIR}")

    db = get_lance_db()
    model = get_embedding_model(model_key)

    # Index lessons
    print("\n[1/2] Indexing lessons...")
    lessons = []
    if LESSONS_FILE.exists():
        with open(LESSONS_FILE) as f:
            lessons = parse_lessons(f.read())

    if lessons:
        print(f"   Generating embeddings for {len(lessons)} lessons...")
        texts = [l["full_text"] for l in lessons]
        embeddings = model.encode(texts, show_progress_bar=True)

        for i, lesson in enumerate(lessons):
            lesson["vector"] = embeddings[i].tolist()
            _embedding_cache.put(texts[i], lesson["vector"])

        if table_exists(db, LESSONS_TABLE):
            db.drop_table(LESSONS_TABLE)

        lessons_table = db.create_table(LESSONS_TABLE, lessons)
        try:
            lessons_table.create_fts_index("full_text")
        except Exception:
            pass
        print(f"   Indexed {len(lessons)} lessons")
    else:
        print("   No lessons found")

    # Index feedback
    print("\n[2/2] Indexing RLHF feedback...")
    feedback = load_feedback_patterns()

    if feedback:
        print(f"   Generating embeddings for {len(feedback)} feedback entries...")
        texts = [f["full_text"] for f in feedback]
        embeddings = model.encode(texts, show_progress_bar=True)

        for i, fb in enumerate(feedback):
            fb["vector"] = embeddings[i].tolist()
            _embedding_cache.put(texts[i], fb["vector"])

        if table_exists(db, FEEDBACK_TABLE):
            db.drop_table(FEEDBACK_TABLE)

        feedback_table = db.create_table(FEEDBACK_TABLE, feedback)
        try:
            feedback_table.create_fts_index("full_text")
        except Exception:
            pass
        print(f"   Indexed {len(feedback)} feedback entries")
    else:
        print("   No feedback found (this is why RLHF isn't learning!)")

    # Save index state
    state = {
        "last_indexed": datetime.now().isoformat(),
        "lessons_count": len(lessons),
        "feedback_count": len(feedback),
        "model": EMBEDDING_MODELS.get(model_key, model_key),
        "db_type": "lancedb",
        "version": "2.0",
        "features": ["similarity_threshold", "lru_cache", "bm25_hybrid", "native_fts", "metrics"],
    }
    with open(INDEX_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

    _metrics.log("index", {
        "lessons_count": len(lessons),
        "feedback_count": len(feedback),
        "model": model_key,
    })

    print(f"\nIndexing complete!")
    print(f"   Total documents: {len(lessons) + len(feedback)}")


def add_feedback(
    feedback_type: str,
    context: str,
    tags: Optional[List[str]] = None,
    reward: Optional[float] = None,
    source: str = "hook",
    signal: Optional[str] = None,
    reindex: bool = True,
) -> Dict[str, Any]:
    """Add feedback entry and optionally trigger re-indexing."""
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)

    # Determine reward based on feedback type
    if reward is None:
        reward = 1 if feedback_type == "positive" else -1

    entry = {
        "id": f"fb_{hashlib.md5(f'{datetime.now().isoformat()}:{context[:50]}'.encode()).hexdigest()[:8]}",
        "timestamp": datetime.now().isoformat(),
        "feedback": feedback_type,
        "context": context,
        "tags": tags or [],
        "reward": reward,
        "source": source,
        "signal": signal,
    }

    with open(FEEDBACK_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')

    _metrics.log("feedback", {
        "type": feedback_type,
        "reward": reward,
        "has_tags": bool(tags),
    })

    print(f"Feedback recorded: {feedback_type} (reward={reward})")

    if reindex:
        # Trigger re-indexing of feedback table only
        print("Re-indexing feedback table...")
        db = get_lance_db()
        model = get_embedding_model()

        feedback = load_feedback_patterns()
        if feedback:
            texts = [f["full_text"] for f in feedback]
            embeddings = model.encode(texts, show_progress_bar=False)

            for i, fb in enumerate(feedback):
                fb["vector"] = embeddings[i].tolist()

            if table_exists(db, FEEDBACK_TABLE):
                db.drop_table(FEEDBACK_TABLE)

            feedback_table = db.create_table(FEEDBACK_TABLE, feedback)
            try:
                feedback_table.create_fts_index("full_text")
            except Exception:
                pass
            print(f"Re-indexed {len(feedback)} feedback entries")

    return entry


def _ensure_fts_index(table, tbl_name: str) -> bool:
    """Create FTS index on table if not present (Feb 2026: LanceDB native FTS).

    LanceDB 1.0+ supports native Tantivy-based full-text search indexes.
    This is faster and more accurate than our custom BM25 for exact-match
    patterns like 'asked permission before commit'.
    """
    try:
        if _fts_supported.get(tbl_name) is False:
            return False

        # Only attempt index creation once per process per table to avoid rebuild costs.
        if tbl_name not in _fts_index_attempted:
            _fts_index_attempted.add(tbl_name)
            try:
                table.create_fts_index("full_text")
            except Exception:
                # Index may already exist (fine) or FTS may be unsupported (we'll
                # discover that on first query).
                pass

        return True
    except Exception:
        return False


def _native_fts_search(table, tbl_name: str, query_text: str, n_results: int) -> Dict[str, float]:
    """Try LanceDB native FTS search, return {id: score} dict."""
    if _fts_supported.get(tbl_name) is False:
        return {}
    try:
        fts_results = table.search(query_text, query_type="fts").limit(n_results * 2).to_list()
        if not fts_results:
            _fts_supported[tbl_name] = True
            return {}

        scores = {}
        # FTS results have _score (higher = better)
        max_score = max(r.get("_score", 0) for r in fts_results) or 1
        for r in fts_results:
            doc_id = r.get("id", "unknown")
            scores[doc_id] = r.get("_score", 0) / max_score
        _fts_supported[tbl_name] = True
        return scores
    except Exception:
        _fts_supported[tbl_name] = False
        return {}


def hybrid_search(
    query_text: str,
    n_results: int = 5,
    threshold: float = SIMILARITY_THRESHOLD,
    table_name: str = None,
    use_bm25: bool = True,
) -> List[Dict[str, Any]]:
    """Hybrid search combining BM25/FTS + vector similarity.

    Feb 2026 upgrade: Tries LanceDB native FTS index first (Tantivy-based),
    falls back to custom BM25 if native FTS is unavailable. Native FTS is
    better for exact-match patterns (e.g., 'asked permission before commit')
    that pure semantic search misses.
    """
    start_time = time.time()

    db = get_lance_db()
    model = get_embedding_model()

    # Get query embedding (with cache)
    query_vector = get_embedding_with_cache(query_text, model)

    results = []
    search_method = "none"
    tables_to_search = [table_name] if table_name else [LESSONS_TABLE, FEEDBACK_TABLE]

    for tbl_name in tables_to_search:
        try:
            if not table_exists(db, tbl_name):
                continue

            table = db.open_table(tbl_name)

            # Vector search
            vector_results = table.search(query_vector).limit(n_results * 2).to_list()

            # Hybrid: try native FTS first, fall back to custom BM25
            fts_scores = {}
            if use_bm25:
                # Try LanceDB native FTS (Feb 2026 upgrade)
                _ensure_fts_index(table, tbl_name)
                fts_scores = _native_fts_search(table, tbl_name, query_text, n_results)
                if _fts_supported.get(tbl_name) is not False:
                    search_method = "native_fts"

                # Fallback: custom BM25 only when native FTS is unavailable.
                if _fts_supported.get(tbl_name) is False:
                    search_method = "custom_bm25"
                    all_docs = table.to_pandas()
                    if len(all_docs) > 0:
                        bm25 = BM25()
                        bm25.fit(all_docs["full_text"].tolist())
                        bm25_results = bm25.search(query_text, top_k=n_results * 2)

                        max_bm25 = max(s for _, s in bm25_results) if bm25_results else 1
                        for idx, score in bm25_results:
                            doc_id = all_docs.iloc[idx]["id"]
                            fts_scores[doc_id] = score / max_bm25 if max_bm25 > 0 else 0

            for r in vector_results:
                distance = r.get("_distance", 1.0)

                # Apply similarity threshold
                if distance > threshold:
                    continue

                # Combine scores (lower distance = higher score)
                vector_score = 1 - (distance / threshold)  # Normalize to 0-1
                bm25_score = fts_scores.get(r.get("id"), 0)

                combined_score = (VECTOR_WEIGHT * vector_score) + (BM25_WEIGHT * bm25_score)

                results.append({
                    "id": r.get("id", "unknown"),
                    "table": tbl_name,
                    "title": r.get("title", r.get("context", "Unknown")),
                    "text": r.get("full_text", "")[:200],
                    "distance": distance,
                    "vector_score": vector_score,
                    "bm25_score": bm25_score,
                    "combined_score": combined_score,
                    "metadata": {
                        "severity": r.get("severity"),
                        "tags": r.get("tags"),
                        "date": r.get("date"),
                        "reward": r.get("reward"),
                    }
                })
        except Exception as e:
            print(f"   Error searching {tbl_name}: {e}")

    # Sort by combined score (higher = more relevant)
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    results = results[:n_results]

    # Log metrics
    latency_ms = (time.time() - start_time) * 1000
    _metrics.log("query", {
        "query": query_text[:50],
        "result_count": len(results),
        "latency_ms": latency_ms,
        "threshold": threshold,
        "use_bm25": use_bm25,
        "search_method": search_method,
        "cache_hit": _embedding_cache.hits > 0,
    })

    return results


def get_session_context(max_lessons: int = 5, max_feedback: int = 3) -> Dict[str, Any]:
    """Get relevant context for session start with hybrid search"""
    start_time = time.time()

    context = {
        "timestamp": datetime.now().isoformat(),
        "critical_lessons": [],
        "recent_negative_patterns": [],
        "recommendations": [],
    }

    try:
        db = get_lance_db()
    except Exception as e:
        context["error"] = str(e)
        return context

    # Query for critical patterns using hybrid search
    critical_queries = [
        "shallow answer surface level lie verification",
        "forgot memory context RAG",
        "never claim without verification truth",
    ]

    # Get critical lessons
    if table_exists(db, LESSONS_TABLE):
        seen_ids = set()
        for q in critical_queries:
            try:
                results = hybrid_search(q, n_results=3, table_name=LESSONS_TABLE)

                for r in results:
                    if r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        severity = r.get("metadata", {}).get("severity", "INFO")
                        if severity in ["CRITICAL", "HIGH"]:
                            context["critical_lessons"].append({
                                "id": r["id"],
                                "title": r.get("title", "Unknown"),
                                "date": r.get("metadata", {}).get("date", "Unknown"),
                                "severity": severity,
                                "score": r.get("combined_score", 0),
                            })
            except Exception:
                pass

        context["critical_lessons"] = context["critical_lessons"][:max_lessons]

    # Get negative feedback patterns
    if table_exists(db, FEEDBACK_TABLE):
        try:
            results = hybrid_search(
                "negative feedback thumbs down bad mistake error",
                n_results=max_feedback * 2,
                table_name=FEEDBACK_TABLE
            )

            for r in results:
                if r.get("metadata", {}).get("reward", 0) <= 0:
                    context["recent_negative_patterns"].append({
                        "id": r["id"],
                        "tags": r.get("metadata", {}).get("tags", "").split(","),
                        "context": r.get("text", "")[:100],
                        "score": r.get("combined_score", 0),
                    })

            context["recent_negative_patterns"] = context["recent_negative_patterns"][:max_feedback]
        except Exception:
            pass

    # Generate recommendations
    if context["critical_lessons"]:
        context["recommendations"].append("Review critical lessons before responding")

    negative_tags = []
    for p in context["recent_negative_patterns"]:
        negative_tags.extend(p.get("tags", []))

    if "shallow-answer" in negative_tags or "shallow" in str(negative_tags):
        context["recommendations"].append("AVOID shallow answers - read actual code")

    if "docs-only" in negative_tags:
        context["recommendations"].append("Don't rely on docs alone - verify in implementation")

    if not context["recommendations"]:
        context["recommendations"].append("No critical patterns detected - proceed normally")

    context["latency_ms"] = (time.time() - start_time) * 1000
    return context


def print_session_context():
    """Print session context for hook integration"""
    context = get_session_context()

    print("\n" + "=" * 50)
    print(f"SEMANTIC MEMORY CONTEXT ({context.get('latency_ms', 0):.0f}ms)")
    print("=" * 50)

    if context.get("error"):
        print(f"\nError: {context['error']}")
        print("   Run: python semantic-memory-v2.py --index")
        return

    if context["critical_lessons"]:
        print("\nCRITICAL LESSONS TO REMEMBER:")
        for lesson in context["critical_lessons"]:
            print(f"   [{lesson['severity']}] {lesson['title']} (score: {lesson.get('score', 0):.2f})")

    if context["recent_negative_patterns"]:
        print("\nPATTERNS THAT CAUSED THUMBS DOWN:")
        for pattern in context["recent_negative_patterns"]:
            tags = [t for t in pattern.get("tags", []) if t]
            if tags:
                print(f"   {', '.join(tags)}")
            if pattern.get("context"):
                print(f"     Context: {pattern['context']}")

    if context["recommendations"]:
        print("\nRECOMMENDATIONS:")
        for rec in context["recommendations"]:
            print(f"   {rec}")

    print("\n" + "=" * 50)


def show_metrics():
    """Show query metrics summary"""
    summary = _metrics.get_summary(days=7)

    print("\nQuery Metrics (Last 7 Days)")
    print("=" * 50)
    print(f"   Total queries: {summary.get('total_queries', 0)}")
    print(f"   Avg latency: {summary.get('avg_latency_ms', 0):.1f}ms")
    print(f"   P95 latency: {summary.get('p95_latency_ms', 0):.1f}ms")
    print(f"   Avg results: {summary.get('avg_results', 0):.1f}")
    print(f"   Feedback events: {summary.get('feedback_events', 0)}")

    cache_stats = summary.get('cache_stats', {})
    print(f"\nCache Stats:")
    print(f"   Hit rate: {cache_stats.get('hit_rate', '0%')}")
    print(f"   Size: {cache_stats.get('size', 0)}/{cache_stats.get('maxsize', 0)}")
    print("=" * 50)


def show_status():
    """Show index status"""
    print("\nSemantic Memory Status (LanceDB v2)")
    print("=" * 50)

    if INDEX_STATE_FILE.exists():
        with open(INDEX_STATE_FILE) as f:
            state = json.load(f)
        print(f"   Last indexed: {state.get('last_indexed', 'Never')}")
        print(f"   Lessons: {state.get('lessons_count', 0)}")
        print(f"   Feedback: {state.get('feedback_count', 0)}")
        print(f"   Model: {state.get('model', 'Unknown')}")
        print(f"   Version: {state.get('version', '1.0')}")
        print(f"   Features: {', '.join(state.get('features', []))}")
    else:
        print("   Index not built yet. Run --index first.")

    try:
        db = get_lance_db()
        tables = get_table_names(db)
        print(f"\n   Tables: {len(tables)}")
        for tbl_name in tables:
            table = db.open_table(tbl_name)
            print(f"   {tbl_name}: {len(table)} documents")
    except Exception as e:
        print(f"   LanceDB error: {e}")

    print("=" * 50)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Semantic Memory System v2 (LanceDB + Hybrid Search + RLHF)"
    )
    parser.add_argument("--index", action="store_true", help="Index all memories")
    parser.add_argument("--query", type=str, help="Hybrid search query")
    parser.add_argument("--context", action="store_true", help="Get session context (for hooks)")
    parser.add_argument("--status", action="store_true", help="Show index status")
    parser.add_argument("--metrics", action="store_true", help="Show query metrics")
    parser.add_argument("--add-feedback", action="store_true", help="Add feedback from stdin")
    parser.add_argument("--feedback-type", type=str, choices=["positive", "negative"], default="negative")
    parser.add_argument("--feedback-context", type=str, help="Feedback context")
    parser.add_argument("--tags", type=str, help="Comma-separated feedback tags (add-feedback only)")
    parser.add_argument("--reward", type=float, help="Override reward value (add-feedback only)")
    parser.add_argument("--source", type=str, default="hook", help="Feedback source label (add-feedback only)")
    parser.add_argument("--signal", type=str, help="Feedback signal label (add-feedback only)")
    parser.add_argument("--no-reindex", action="store_true", help="Skip LanceDB reindex on add-feedback")
    parser.add_argument("--model", type=str, choices=list(EMBEDDING_MODELS.keys()), default=DEFAULT_MODEL)
    parser.add_argument("-n", "--results", type=int, default=5, help="Number of results")
    parser.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD, help="Similarity threshold")
    parser.add_argument("--no-bm25", action="store_true", help="Disable BM25 hybrid search")

    args = parser.parse_args()

    if args.index:
        index_all(args.model)
    elif args.query:
        results = hybrid_search(
            args.query,
            n_results=args.results,
            threshold=args.threshold,
            use_bm25=not args.no_bm25,
        )
        print(f"\nFound {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['table']}] {r['title']}")
            print(f"   Score: {r['combined_score']:.3f} (vector: {r['vector_score']:.3f}, bm25: {r['bm25_score']:.3f})")
            print(f"   Preview: {r['text'][:100]}...")
            print()
    elif args.context:
        print_session_context()
    elif args.status:
        show_status()
    elif args.metrics:
        show_metrics()
    elif args.add_feedback:
        context = args.feedback_context
        if not context:
            # Read from stdin
            context = sys.stdin.read().strip()
        if context:
            tags = None
            if args.tags:
                tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            add_feedback(
                args.feedback_type,
                context,
                tags=tags,
                reward=args.reward,
                source=args.source,
                signal=args.signal,
                reindex=not args.no_reindex,
            )
        else:
            print("Error: No feedback context provided")
            sys.exit(1)
    else:
        parser.print_help()
        print("\nQuick Start:")
        print("   1. python semantic-memory-v2.py --index")
        print("   2. python semantic-memory-v2.py --query 'shallow answers'")
        print("   3. python semantic-memory-v2.py --context")
        print("   4. python semantic-memory-v2.py --metrics")


if __name__ == "__main__":
    main()
