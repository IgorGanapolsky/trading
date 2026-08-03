"""Pragmatic hybrid retrieval for trading lessons.

Lexical first-stage: keyword overlap + character bigram-Jaccard + severity/recency
boosts. Optional FTS5 candidate seed is fused via Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Iterable, Optional

STOP = {
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
    "then",
}

DOMAIN_EXPANSIONS: dict[str, list[str]] = {
    "put credit": ["short put spread", "credit spread", "bull put", "15 delta"],
    "iron condor": ["4-leg", "defined risk", "short strangle", "7 dte", "exit", "management"],
    "stop loss": ["200% credit", "hard stop", "max loss"],
    "position sizing": ["1-lot", "lot size", "max concurrent", "accumulation", "position limit"],
    "position sizing error": ["accumulation bug", "5pct", "lot size", "hardcoded"],
    "close position": ["close_position", "alpaca", "orphan", "buy to close", "api bug"],
    "api bug": ["alpaca", "close_position", "sdk", "endpoint"],
    "circuit breaker": ["trading halt", "kill switch", "drawdown"],
    "exit strategy": ["7 dte", "profit target", "25%", "management", "adjustment"],
    "win rate": ["expectancy", "profit factor", "71k", "research"],
    "sofi": ["pdt", "blocked", "individual stock", "blacklist"],
    "delta": ["15 delta", "20 delta", "short strike", "selection"],
    "rag webhook": ["lancedb", "semantic search", "cloud run", "query"],
}


def tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.split(r"[^a-z0-9_\-]+", (text or "").lower())
        if len(t) > 2 and t not in STOP
    ]


def text_bigrams(text: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) < 2:
        return set()
    return {normalized[i : i + 2] for i in range(len(normalized) - 1)}


def bigram_jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: float = 60.0,
    weights: Optional[list[float]] = None,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for list_i, ids in enumerate(ranked_lists):
        w = 1.0
        if weights and list_i < len(weights):
            w = float(weights[list_i]) or 1.0
        for rank, doc_id in enumerate(ids, start=1):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _severity_boost(severity: str) -> float:
    s = (severity or "").upper()
    if s == "CRITICAL":
        return 0.25
    if s == "HIGH":
        return 0.15
    if s == "MEDIUM":
        return 0.05
    return 0.0


def _recency_boost(lesson: dict[str, Any]) -> float:
    # Prefer explicit timestamp; else boost ids that look recent by month token.
    ts = lesson.get("timestamp") or lesson.get("updated_at")
    if ts:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            age_days = max(0.0, (datetime.now(UTC) - dt.astimezone(UTC)).days)
            if age_days <= 7:
                return 0.2
            if age_days <= 30:
                return 0.12
            if age_days <= 90:
                return 0.05
        except ValueError:
            pass
    lid = str(lesson.get("id", "")).lower()
    month = datetime.now(UTC).strftime("%b").lower()[:3]
    if month in lid:
        return 0.1
    return 0.0


def score_relevance(lesson: dict[str, Any], query: str) -> float:
    """Keyword + path-ish token overlap + bigram Jaccard (when base signal > 0)."""
    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0

    title = str(lesson.get("title") or "")
    content = str(lesson.get("content") or lesson.get("snippet") or "")
    prevention = str(lesson.get("prevention") or "")
    tags = " ".join(str(t) for t in (lesson.get("tags") or []))
    blob = f"{title}\n{content}\n{prevention}\n{tags}".lower()
    doc_tokens = set(tokenize(blob))

    score = 0.0
    hits = sum(1 for t in q_tokens if t in doc_tokens or t in blob)
    score += min(hits * 0.08, 0.48)

    # Title / prevention exact-ish boosts
    title_hits = sum(1 for t in q_tokens if t in title.lower())
    score += min(title_hits * 0.06, 0.24)
    prev_hits = sum(1 for t in q_tokens if t in prevention.lower())
    score += min(prev_hits * 0.05, 0.2)

    score += _severity_boost(str(lesson.get("severity") or ""))
    score += _recency_boost(lesson)

    # Lesson id / filename token boost (e.g. close_position, sofi, lot)
    lid = str(lesson.get("id") or "").lower().replace("-", "_")
    id_hits = sum(1 for t in q_tokens if t in lid)
    score += min(id_hits * 0.1, 0.3)

    if score > 0:
        bj = bigram_jaccard(text_bigrams(query), text_bigrams(blob[:4000]))
        score += bj * 0.25

    return min(score, 1.5)


def expand_query_terms(query: str) -> list[str]:
    q = (query or "").lower()
    added: list[str] = []
    for key, terms in DOMAIN_EXPANSIONS.items():
        if key in q:
            for t in terms:
                if t not in q:
                    added.append(t)
    return added[:6]


def build_query_variants(query: str, *, max_variants: int = 3) -> list[str]:
    original = (query or "").strip()
    if not original:
        return []
    expansions = expand_query_terms(original)
    variants = [original]
    if expansions:
        variants.append(f"{original} {' '.join(expansions[:4])}".strip())
    focused_terms = [t for t in tokenize(original) if len(t) >= 3][:12]
    focused_terms.extend(expansions[:4])
    if focused_terms:
        variants.append(
            "trading failure prevention " + " ".join(dict.fromkeys(focused_terms))
        )
    # Dedupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for v in variants:
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v[:500])
        if len(out) >= max_variants:
            break
    return out


def pragmatic_hybrid_search(
    corpus: list[dict[str, Any]],
    query: str,
    *,
    fts_ranked_ids: Optional[list[str]] = None,
    query_variants: Optional[list[str]] = None,
    top_k: int = 10,
    pool: int = 50,
    rrf_k: float = 60.0,
) -> dict[str, Any]:
    """Hybrid lexical multi-query + optional FTS list fused with RRF."""
    variants = list(query_variants or [query])
    variants = [v for v in variants if v and str(v).strip()] or [query]

    by_id = {str(d.get("id")): d for d in corpus if d.get("id")}
    lexical_lists: list[list[str]] = []
    best_scores: dict[str, float] = {}

    for variant in variants:
        scored: list[tuple[str, float]] = []
        for doc in corpus:
            doc_id = str(doc.get("id") or "")
            if not doc_id:
                continue
            s = score_relevance(doc, variant)
            if s > 0.08:
                scored.append((doc_id, s))
                if s > best_scores.get(doc_id, 0.0):
                    best_scores[doc_id] = s
        scored.sort(key=lambda x: x[1], reverse=True)
        lexical_lists.append([doc_id for doc_id, _ in scored[:pool]])

    lists = list(lexical_lists)
    weights = [1.0] * len(lists)
    if fts_ranked_ids:
        lists.append(list(fts_ranked_ids)[:pool])
        weights.append(1.25)

    fused = reciprocal_rank_fusion(lists, k=rrf_k, weights=weights)
    results: list[dict[str, Any]] = []
    for doc_id, rrf in fused[:pool]:
        doc = by_id.get(doc_id)
        if not doc:
            continue
        lexical = best_scores.get(doc_id, 0.0)
        combined = 0.55 * min(lexical, 1.0) + 0.45 * min(rrf * 10.0, 1.0)
        row = {
            **doc,
            "lexical_score": lexical,
            "rrf_score": rrf,
            "score": combined,
            "relevanceScore": combined,
        }
        results.append(row)

    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "results": results[:top_k],
        "meta": {
            "strategy": "pragmatic-hybrid-rrf",
            "query_variants": variants,
            "lexical_lists": len(lexical_lists),
            "fts_fused": bool(fts_ranked_ids),
            "pool": pool,
        },
    }


def probe_top_lexical(corpus: Iterable[dict[str, Any]], query: str) -> float:
    top = 0.0
    for doc in corpus:
        top = max(top, score_relevance(doc, query))
    return top
