"""Index-first context bundle engine.

Builds a compact retrieval index from local knowledge sources and serves a
single "super retrieve" interface suitable for agent runtime usage.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "our",
    "are",
    "was",
    "were",
    "how",
    "what",
    "when",
    "where",
    "which",
    "about",
    "after",
    "before",
    "they",
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
}


@dataclass
class BundleDoc:
    id: str
    source: str
    title: str
    text: str
    tags: list[str]
    timestamp: str | None = None
    metadata: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _tokenize(text: str) -> list[str]:
    raw = re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())
    return [tok for tok in raw if len(tok) > 1 and tok not in STOPWORDS]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


class ContextBundleEngine:
    """Precompute and query context bundles with BM25 + recency ranking."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.index_dir = self.project_root / "data" / "context_engine"
        self.index_file = self.index_dir / "context_index.json"
        self._git_tracked_paths = self._load_git_tracked_paths()

    def _load_git_tracked_paths(self) -> set[str] | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.project_root), "ls-files"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return tracked or None

    def _is_git_tracked(self, file_path: Path) -> bool:
        if self._git_tracked_paths is None:
            return True
        try:
            rel_path = file_path.relative_to(self.project_root).as_posix()
        except ValueError:
            return False
        return rel_path in self._git_tracked_paths

    def build_index(self, *, top_per_source: int = 500) -> dict[str, Any]:
        docs = self._collect_docs(top_per_source=top_per_source)
        idf, avgdl, tf_by_doc = self._build_bm25_state(docs)
        payload = {
            "built_at": _now_iso(),
            "doc_count": len(docs),
            "avg_doc_len": avgdl,
            "idf": idf,
            "docs": [
                {
                    "id": doc.id,
                    "source": doc.source,
                    "title": doc.title,
                    "text": doc.text,
                    "tags": doc.tags,
                    "timestamp": doc.timestamp,
                    "metadata": doc.metadata or {},
                }
                for doc in docs
            ],
            "tf": tf_by_doc,
            "sources": dict(Counter(doc.source for doc in docs)),
        }
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "index_file": str(self.index_file),
            "doc_count": len(docs),
            "sources": payload["sources"],
            "vocab_size": len(idf),
            "built_at": payload["built_at"],
        }

    def super_retrieve(
        self, query: str, *, top_k: int = 8, min_score: float = 0.01
    ) -> dict[str, Any]:
        index = self._load_index()
        if not index.get("docs"):
            return {"query": query, "results": [], "context": "", "meta": {"index_empty": True}}

        terms = _tokenize(query)
        if not terms:
            return {
                "query": query,
                "results": [],
                "context": "",
                "meta": {"index_empty": False, "reason": "empty_query_terms"},
            }

        idf = index.get("idf", {})
        tf_map = index.get("tf", {})
        avgdl = float(index.get("avg_doc_len", 1.0)) or 1.0
        docs = index["docs"]
        now = datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []
        max_raw = 0.0

        for doc in docs:
            doc_id = doc["id"]
            tf = tf_map.get(doc_id, {})
            dl = float(sum(tf.values()) or 1.0)
            bm25 = self._bm25(terms, tf, idf, dl, avgdl)
            recency = self._recency_boost(now, _parse_time(doc.get("timestamp")))
            source_boost = self._source_boost(doc.get("source", "unknown"))
            score = (0.78 * bm25) + (0.17 * recency) + (0.05 * source_boost)
            max_raw = max(max_raw, score)
            results.append(
                {
                    "id": doc_id,
                    "source": doc.get("source"),
                    "title": doc.get("title"),
                    "score_raw": score,
                    "recency_boost": recency,
                    "source_boost": source_boost,
                    "timestamp": doc.get("timestamp"),
                    "tags": doc.get("tags", []),
                    "text": doc.get("text", ""),
                    "metadata": doc.get("metadata", {}),
                }
            )

        if max_raw > 0.0:
            for row in results:
                row["score"] = round(row["score_raw"] / max_raw, 4)
        else:
            for row in results:
                row["score"] = 0.0

        ranked = sorted(results, key=lambda x: x["score"], reverse=True)
        filtered = [row for row in ranked if row["score"] >= min_score][:top_k]
        context = self._assemble_context(filtered)
        compact = [
            {
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "score": row["score"],
                "timestamp": row["timestamp"],
                "tags": row["tags"],
                "snippet": _normalize_text(row["text"])[:240],
                "metadata": row["metadata"],
            }
            for row in filtered
        ]
        return {
            "query": query,
            "results": compact,
            "context": context,
            "meta": {
                "index_file": str(self.index_file),
                "index_doc_count": len(docs),
                "returned": len(compact),
            },
        }

    def _load_index(self) -> dict[str, Any]:
        if not self.index_file.exists():
            self.build_index()
        try:
            loaded = json.loads(self.index_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"docs": [], "idf": {}, "tf": {}, "avg_doc_len": 1.0}
        if isinstance(loaded, dict):
            return loaded
        return {"docs": [], "idf": {}, "tf": {}, "avg_doc_len": 1.0}

    def _build_bm25_state(
        self, docs: list[BundleDoc]
    ) -> tuple[dict[str, float], float, dict[str, dict[str, int]]]:
        tf_by_doc: dict[str, dict[str, int]] = {}
        df: Counter[str] = Counter()
        lengths: list[int] = []

        for doc in docs:
            tokens = _tokenize(f"{doc.title} {doc.text} {' '.join(doc.tags)}")
            tf = dict(Counter(tokens))
            tf_by_doc[doc.id] = tf
            lengths.append(sum(tf.values()))
            for term in tf:
                df[term] += 1

        n_docs = len(docs)
        avgdl = float(sum(lengths) / n_docs) if n_docs else 1.0
        idf: dict[str, float] = {}
        for term, freq in df.items():
            idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)
        return idf, avgdl, tf_by_doc

    def _bm25(
        self,
        terms: list[str],
        tf: dict[str, int],
        idf: dict[str, float],
        dl: float,
        avgdl: float,
        *,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> float:
        score = 0.0
        for term in terms:
            freq = float(tf.get(term, 0))
            if freq <= 0:
                continue
            idf_term = float(idf.get(term, 0.0))
            denom = freq + k1 * (1 - b + b * (dl / avgdl))
            if denom > 0:
                score += idf_term * ((freq * (k1 + 1.0)) / denom)
        return score

    def _recency_boost(self, now: datetime, timestamp: datetime | None) -> float:
        if timestamp is None:
            return 0.1
        age_days = max(0.0, (now - timestamp).total_seconds() / 86400.0)
        return max(0.1, math.exp(-age_days / 30.0))

    def _source_boost(self, source: str) -> float:
        source_weights = {
            "feedback": 1.0,
            "thompson": 1.0,
            "lesson": 0.95,
            "rag_query": 0.9,
        }
        return source_weights.get(source, 0.6)

    def _assemble_context(self, rows: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for idx, row in enumerate(rows, start=1):
            lines.append(
                f"[{idx}] ({row['source']}) {row['title']} | score={row['score']:.3f} | "
                f"tags={','.join(row.get('tags', []))}"
            )
            lines.append(_normalize_text(row.get("text", ""))[:600])
        return "\n".join(lines)

    def _collect_docs(self, *, top_per_source: int) -> list[BundleDoc]:
        docs: list[BundleDoc] = []
        docs.extend(self._load_lessons(top_per_source=top_per_source))
        docs.extend(self._load_rag_query_json(top_per_source=top_per_source))
        docs.extend(self._load_feedback_thompson(top_per_source=top_per_source))
        deduped: dict[str, BundleDoc] = {}
        for doc in docs:
            deduped[f"{doc.source}:{doc.id}"] = doc
        return list(deduped.values())

    def _load_lessons(self, *, top_per_source: int) -> list[BundleDoc]:
        path = self.project_root / "rag_knowledge" / "lessons_learned"
        if not path.exists():
            return []
        files = [
            file_path for file_path in sorted(path.glob("*.md")) if self._is_git_tracked(file_path)
        ][-top_per_source:]
        docs: list[BundleDoc] = []
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            title = lines[0].lstrip("# ").strip() if lines else file_path.stem
            severity_match = re.search(r"\*\*Severity\*\*:\s*([A-Z]+)", text)
            severity = severity_match.group(1) if severity_match else "MEDIUM"
            tags = [severity.lower(), "lesson"]
            docs.append(
                BundleDoc(
                    id=file_path.stem,
                    source="lesson",
                    title=title,
                    text=_normalize_text(text),
                    tags=tags,
                    timestamp=datetime.fromtimestamp(
                        file_path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    metadata={
                        "path": str(file_path.relative_to(self.project_root)),
                        "severity": severity,
                    },
                )
            )
        return docs

    def _load_rag_query_json(self, *, top_per_source: int) -> list[BundleDoc]:
        profile = os.getenv("RAG_WRITE_PROFILE", "").strip().lower()
        repo_path = self.project_root / "data" / "rag" / "lessons_query.json"
        local_path = self.project_root / "artifacts" / "local" / "rag" / "lessons_query.json"
        if profile == "repo":
            path = repo_path
        elif profile == "local":
            path = local_path
        else:
            path = repo_path if repo_path.exists() else local_path
        if not path.exists() or not self._is_git_tracked(path):
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        docs: list[BundleDoc] = []
        for idx, item in enumerate(payload[-top_per_source:]):
            if not isinstance(item, dict):
                continue
            docs.append(
                BundleDoc(
                    id=str(item.get("id") or f"rag-query-{idx}"),
                    source="rag_query",
                    title=str(item.get("title") or "RAG Lesson"),
                    text=_normalize_text(str(item.get("content") or "")),
                    tags=[str(tag) for tag in item.get("tags", []) if isinstance(tag, str)],
                    timestamp=(
                        item.get("timestamp")
                        or item.get("event_timestamp_utc")
                        or item.get("indexed_at_utc")
                        or item.get("source_mtime_utc")
                    ),
                    metadata={"rank": item.get("rank"), "source": item.get("source")},
                )
            )
        return docs

    def _load_feedback_thompson(self, *, top_per_source: int) -> list[BundleDoc]:
        path = self.project_root / ".claude" / "memory" / "feedback" / "thompson_feedback_log.jsonl"
        if not path.exists() or not self._is_git_tracked(path):
            return []
        docs: list[BundleDoc] = []
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for idx, line in enumerate(lines[-top_per_source:]):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            context = str(row.get("context_preview") or row.get("user_message_preview") or "")
            docs.append(
                BundleDoc(
                    id=str(row.get("event_key") or f"thompson-{idx}"),
                    source="thompson",
                    title=f"Feedback {row.get('feedback_type', 'unknown')}",
                    text=_normalize_text(context),
                    tags=[str(row.get("feedback_type", "")), "feedback", "thompson"],
                    timestamp=row.get("timestamp"),
                    metadata={
                        "delta_mean": row.get("bandit", {}).get("delta_mean")
                        if isinstance(row.get("bandit"), dict)
                        else None,
                        "signal": row.get("signal"),
                    },
                )
            )
        return docs
