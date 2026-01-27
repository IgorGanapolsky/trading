#!/usr/bin/env python3
"""
Semantic Memory System v2 - Enhanced RAG/ML Infrastructure for Trading System

Adapted from Random-Timer project (Jan 27, 2026)

FEATURES:
1. Similarity threshold filtering (no irrelevant results)
2. LRU cache for embeddings (faster repeated queries)
3. BM25 hybrid search (keyword + vector fusion)
4. Active RLHF feedback loop (auto-reindex on feedback)
5. Query metrics logging (precision/recall tracking)
6. Trading-specific lesson patterns

Architecture:
┌─────────────────────────────────────────────────────────┐
│  HYBRID SEARCH ENGINE                                   │
│  ┌────────────────┐  ┌────────────────┐                │
│  │ BM25 (Keywords)│ + │ Vector (Semantic)│ = Fusion    │
│  └────────────────┘  └────────────────┘                │
└─────────────────────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  LanceDB Storage    │
              │  + Similarity Filter │
              │  + LRU Cache        │
              └─────────────────────┘

Usage:
  python semantic-memory-v2.py --index              # Index all memories
  python semantic-memory-v2.py --query "shallow"    # Hybrid search
  python semantic-memory-v2.py --context            # Get session context
  python semantic-memory-v2.py --add-feedback       # Add RLHF feedback (stdin)
  python semantic-memory-v2.py --metrics            # Show query metrics
"""

import hashlib
import json
import os
import re
import sys
import time
from collections import OrderedDict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuration
SCRIPT_DIR = Path(__file__).parent
CLAUDE_DIR = SCRIPT_DIR.parent.parent
MEMORY_DIR = CLAUDE_DIR / "memory"
RAG_DIR = Path(__file__).parent.parent.parent.parent / "rag_knowledge" / "lessons_learned"
FEEDBACK_DIR = MEMORY_DIR / "feedback"
LANCE_DIR = MEMORY_DIR / "lancedb"
INDEX_STATE_FILE = FEEDBACK_DIR / "lance-index-state.json"
METRICS_FILE = FEEDBACK_DIR / "query-metrics.jsonl"
FEEDBACK_LOG = FEEDBACK_DIR / "feedback-log.jsonl"

# Model options
EMBEDDING_MODELS = {
    "fast": "all-MiniLM-L6-v2",       # 384 dims, ~50ms
    "better": "intfloat/e5-small-v2",  # 384 dims, ~80ms, better quality
    "best": "intfloat/e5-base-v2",     # 768 dims, ~150ms, highest quality
}
DEFAULT_MODEL = "fast"  # Start with fast, upgrade if needed

# Search configuration
SIMILARITY_THRESHOLD = 0.8  # Euclidean distance threshold (lower = more similar)
BM25_WEIGHT = 0.3           # Weight for BM25 in hybrid search
VECTOR_WEIGHT = 0.7         # Weight for vector similarity

# Table names
LESSONS_TABLE = "lessons_learned"
FEEDBACK_TABLE = "rlhf_feedback"


def get_table_names(db) -> List[str]:
    """Get table names from LanceDB, handling different API versions."""
    result = db.table_names()
    if hasattr(result, 'tables'):
        return result.tables
    return list(result)


def table_exists(db, table_name: str) -> bool:
    """Check if a table exists in LanceDB."""
    return table_name in get_table_names(db)


# LRU Cache for embeddings
class EmbeddingCache:
    """Thread-safe LRU cache for embeddings"""
    def __init__(self, maxsize: int = 1000):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

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
    """Get sentence transformer model with caching"""
    try:
        from sentence_transformers import SentenceTransformer
        model_name = EMBEDDING_MODELS.get(model_key, EMBEDDING_MODELS["fast"])

        # Use persistent cache directory
        cache_dir = MEMORY_DIR / "model_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(cache_dir))

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


def parse_rag_lessons() -> List[Dict[str, Any]]:
    """Parse lessons from rag_knowledge/lessons_learned/ directory"""
    lessons = []

    if not RAG_DIR.exists():
        print(f"   RAG directory not found: {RAG_DIR}")
        return lessons

    for md_file in RAG_DIR.glob("*.md"):
        try:
            content = md_file.read_text()
            filename = md_file.stem

            # Extract lesson ID from filename (e.g., ll_220_iron_condor_math)
            lesson_id = filename

            # Extract title from first # heading
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename

            # Determine severity from content
            severity = "INFO"
            if "CRITICAL" in content[:500] or "critical" in filename:
                severity = "CRITICAL"
            elif "HIGH" in content[:500] or "important" in filename:
                severity = "HIGH"

            # Extract tags from content
            tags = []
            tag_patterns = [
                ("iron-condor", ["iron condor", "iron_condor"]),
                ("risk", ["risk", "stop-loss", "stop loss"]),
                ("win-rate", ["win rate", "win_rate", "probability"]),
                ("tax", ["tax", "1256", "wash sale"]),
                ("delta", ["delta", "15-delta", "20-delta"]),
                ("dte", ["dte", "expiration", "7 dte"]),
                ("phil-town", ["phil town", "rule 1", "rule #1"]),
            ]
            for tag, keywords in tag_patterns:
                if any(kw in content.lower() for kw in keywords):
                    tags.append(tag)

            lessons.append({
                "id": f"lesson_{lesson_id}",
                "date": "2026-01-27",  # Use current date
                "title": title,
                "severity": severity,
                "tags": ",".join(tags),
                "content": content[:1000],
                "full_text": f"{title}\n\nSeverity: {severity}\nTags: {', '.join(tags)}\n\n{content[:2000]}",
                "source_file": str(md_file),
            })
        except Exception as e:
            print(f"   Error parsing {md_file}: {e}")

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
                    doc_text = f"Feedback: {entry.get('feedback', 'unknown')}\n"
                    doc_text += f"Context: {entry.get('context', entry.get('message', ''))}\n"
                    doc_text += f"Tags: {', '.join(entry.get('tags', []))}\n"
                    doc_text += f"Action: {entry.get('actionType', 'unknown')}"

                    patterns.append({
                        "id": entry.get("id", f"fb_{len(patterns)}"),
                        "type": "feedback",
                        "feedback_type": entry.get("feedback", "unknown"),
                        "reward": entry.get("reward", -1 if entry.get("feedback") == "negative" else 1),
                        "context": entry.get("context", entry.get("message", ""))[:200],
                        "tags": ",".join(entry.get("tags", [])),
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

    # Index lessons from RAG
    print("\n[1/2] Indexing RAG lessons...")
    lessons = parse_rag_lessons()

    if lessons:
        print(f"   Generating embeddings for {len(lessons)} lessons...")
        texts = [lesson["full_text"] for lesson in lessons]
        embeddings = model.encode(texts, show_progress_bar=True)

        for i, lesson in enumerate(lessons):
            lesson["vector"] = embeddings[i].tolist()
            _embedding_cache.put(texts[i], lesson["vector"])

        if table_exists(db, LESSONS_TABLE):
            db.drop_table(LESSONS_TABLE)

        db.create_table(LESSONS_TABLE, lessons)
        print(f"   Indexed {len(lessons)} lessons")
    else:
        print("   No lessons found in rag_knowledge/lessons_learned/")

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

        db.create_table(FEEDBACK_TABLE, feedback)
        print(f"   Indexed {len(feedback)} feedback entries")
    else:
        print("   No feedback found yet - give thumbs up/down to start learning!")

    # Save index state
    state = {
        "last_indexed": datetime.now().isoformat(),
        "lessons_count": len(lessons),
        "feedback_count": len(feedback),
        "model": EMBEDDING_MODELS.get(model_key, model_key),
        "db_type": "lancedb",
        "version": "2.0",
        "features": ["similarity_threshold", "lru_cache", "bm25_hybrid", "metrics"],
    }
    INDEX_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

    _metrics.log("index", {
        "lessons_count": len(lessons),
        "feedback_count": len(feedback),
        "model": model_key,
    })

    print(f"\nIndexing complete!")
    print(f"   Total documents: {len(lessons) + len(feedback)}")


def add_feedback(feedback_type: str, context: str, tags: List[str] = None, reward: int = None):
    """Add feedback entry and trigger re-indexing"""
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)

    if reward is None:
        reward = 1 if feedback_type == "positive" else -1

    entry = {
        "id": f"fb_{hashlib.md5(f'{datetime.now().isoformat()}:{context[:50]}'.encode()).hexdigest()[:8]}",
        "timestamp": datetime.now().isoformat(),
        "feedback": feedback_type,
        "context": context,
        "tags": tags or [],
        "reward": reward,
    }

    with open(FEEDBACK_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')

    _metrics.log("feedback", {
        "type": feedback_type,
        "reward": reward,
        "has_tags": bool(tags),
    })

    print(f"Feedback recorded: {feedback_type} (reward={reward})")

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

        db.create_table(FEEDBACK_TABLE, feedback)
        print(f"Re-indexed {len(feedback)} feedback entries")

    return entry


def hybrid_search(
    query_text: str,
    n_results: int = 5,
    threshold: float = SIMILARITY_THRESHOLD,
    table_name: str = None,
    use_bm25: bool = True,
) -> List[Dict[str, Any]]:
    """Hybrid search combining BM25 + vector similarity"""
    start_time = time.time()

    db = get_lance_db()
    model = get_embedding_model()

    query_vector = get_embedding_with_cache(query_text, model)

    results = []
    tables_to_search = [table_name] if table_name else [LESSONS_TABLE, FEEDBACK_TABLE]

    for tbl_name in tables_to_search:
        try:
            if not table_exists(db, tbl_name):
                continue

            table = db.open_table(tbl_name)
            all_docs = table.to_pandas()

            # Vector search
            vector_results = table.search(query_vector).limit(n_results * 2).to_list()

            # BM25 search (if enabled)
            bm25_scores = {}
            if use_bm25 and len(all_docs) > 0:
                bm25 = BM25()
                bm25.fit(all_docs["full_text"].tolist())
                bm25_results = bm25.search(query_text, top_k=n_results * 2)

                max_bm25 = max(s for _, s in bm25_results) if bm25_results else 1
                for idx, score in bm25_results:
                    doc_id = all_docs.iloc[idx]["id"]
                    bm25_scores[doc_id] = score / max_bm25 if max_bm25 > 0 else 0

            for r in vector_results:
                distance = r.get("_distance", 1.0)

                if distance > threshold:
                    continue

                vector_score = 1 - (distance / threshold)
                bm25_score = bm25_scores.get(r.get("id"), 0)

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

    results.sort(key=lambda x: x['combined_score'], reverse=True)
    results = results[:n_results]

    latency_ms = (time.time() - start_time) * 1000
    _metrics.log("query", {
        "query": query_text[:50],
        "result_count": len(results),
        "latency_ms": latency_ms,
        "threshold": threshold,
        "use_bm25": use_bm25,
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

    # Trading-specific critical queries
    critical_queries = [
        "iron condor risk management stop loss",
        "verification evidence proof claim",
        "Phil Town Rule 1 don't lose money",
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
        context["recommendations"].append("Review critical trading lessons before responding")

    negative_tags = []
    for p in context["recent_negative_patterns"]:
        negative_tags.extend(p.get("tags", []))

    if "shallow-answer" in negative_tags:
        context["recommendations"].append("AVOID shallow answers - read actual code")

    if "verification" in negative_tags:
        context["recommendations"].append("Always verify claims with evidence")

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
            print(f"   [{lesson['severity']}] {lesson['title'][:50]}... (score: {lesson.get('score', 0):.2f})")

    if context["recent_negative_patterns"]:
        print("\nPATTERNS THAT CAUSED THUMBS DOWN:")
        for pattern in context["recent_negative_patterns"]:
            tags = [t for t in pattern.get("tags", []) if t]
            if tags:
                print(f"   {', '.join(tags)}")
            if pattern.get("context"):
                print(f"     Context: {pattern['context'][:80]}...")

    if context["recommendations"]:
        print("\nRECOMMENDATIONS:")
        for rec in context["recommendations"]:
            print(f"   - {rec}")

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
            print(f"   - {tbl_name}: {len(table)} documents")
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
            print(f"{i}. [{r['table']}] {r['title'][:60]}...")
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
            context = sys.stdin.read().strip()
        if context:
            add_feedback(args.feedback_type, context)
        else:
            print("Error: No feedback context provided")
            sys.exit(1)
    else:
        parser.print_help()
        print("\nQuick Start:")
        print("   1. python semantic-memory-v2.py --index")
        print("   2. python semantic-memory-v2.py --query 'iron condor risk'")
        print("   3. python semantic-memory-v2.py --context")
        print("   4. python semantic-memory-v2.py --metrics")


if __name__ == "__main__":
    main()
