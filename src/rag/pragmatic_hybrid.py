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
    "iron condor": [
        "4-leg",
        "defined risk",
        "short strangle",
        "7 dte",
        "exit",
        "management",
        "ic",
        "adjustment",
    ],
    "exit strategy": [
        "7 dte",
        "profit target",
        "25%",
        "management",
        "adjustment",
        "win rate",
        "position management",
        "ic position management",
        "71k study",
        "management system",
    ],
    "iron condor exit": [
        "position management",
        "management system",
        "71k",
        "adjustment",
        "win rate research",
        "7 dte exit",
    ],
    "stop loss": ["200% credit", "hard stop", "max loss"],
    "position sizing": [
        "1-lot",
        "lot size",
        "max concurrent",
        "accumulation",
        "position limit",
        "5pct",
        "aggregate",
        "hardcoded",
        "aggregate exposure",
        "position accumulation",
    ],
    "position sizing error": [
        "accumulation bug",
        "position accumulation",
        "5pct",
        "5% limit",
        "lot size",
        "hardcoded",
        "aggregate risk",
        "aggregate exposure",
        "position limit",
        "position accumulation bug",
        "accumulation",
        "aggregate_position_risk",
        "5pct_position_limit",
    ],
    "close position": [
        "close_position",
        "alpaca",
        "orphan",
        "buy to close",
        "api bug",
        "workflow",
        "submit_order",
        "atomic",
        "exit ownership",
    ],
    "api bug": ["alpaca", "close_position", "sdk", "endpoint", "workflow"],
    "circuit breaker": ["trading halt", "kill switch", "drawdown"],
    "win rate": ["expectancy", "profit factor", "71k", "research", "management"],
    "sofi": [
        "pdt",
        "blocked",
        "individual stock",
        "blacklist",
        "blackout",
        "ticker",
        "crisis",
        "spy-only",
        "legacy position",
    ],
    "blocked trading": ["sofi", "pdt", "halt", "blackout", "crisis", "ci failure"],
    "delta": ["15 delta", "20 delta", "short strike", "selection", "vix", "entry"],
    "delta selection": ["15 delta", "short strike", "vix entry", "iron condor", "win rate"],
    "rag webhook": ["lancedb", "semantic search", "cloud run", "query", "routing"],
    "financial independence": ["north star", "roadmap", "wealth", "6000"],
    "tax optimization": ["xsp", "section 1256", "60/40", "spy"],
    "entry signals": ["vix", "timing", "iron condor entry", "delta"],
}

# Tokens that are trading-domain anchors; absence on OOD queries helps reject noise.
TRADING_ANCHOR_TOKENS = frozenset(
    {
        "spy",
        "xsp",
        "spx",
        "qqq",
        "sofi",
        "alpaca",
        "iron",
        "condor",
        "credit",
        "put",
        "call",
        "delta",
        "dte",
        "vix",
        "pdt",
        "lot",
        "stop",
        "drawdown",
        "rag",
        "lancedb",
        "webhook",
        "tax",
        "north",
        "star",
        "roadmap",
        "orphan",
        "position",
        "sizing",
        "close",
        "api",
        "bug",
        "exit",
        "entry",
        "spread",
        "options",
        "broker",
        "gateway",
    }
)


def tokenize(text: str) -> list[str]:
    return [
        t for t in re.split(r"[^a-z0-9_\-]+", (text or "").lower()) if len(t) > 2 and t not in STOP
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


def _token_match(token: str, haystack_tokens: set[str], haystack: str) -> bool:
    """Exact token match or light prefix/stem match (error↔errors, size↔sizing)."""
    if token in haystack_tokens or token in haystack:
        return True
    if len(token) < 4:
        return False
    for ht in haystack_tokens:
        if len(ht) < 4:
            continue
        if ht.startswith(token[:4]) or token.startswith(ht[:4]):
            return True
        # crude stem: drop trailing s/ed/ing
        for a, b in ((token.rstrip("s"), ht.rstrip("s")), (token[: max(4, len(token) - 3)], ht)):
            if a and b and (a == b or a in b or b in a) and len(a) >= 4:
                return True
    return False


def score_relevance(lesson: dict[str, Any], query: str) -> float:
    """Keyword + path token overlap + phrase + bigram Jaccard + domain expansion."""
    q_raw = (query or "").strip()
    expansions = expand_query_terms(q_raw)
    expanded_query = f"{q_raw} {' '.join(expansions)}".strip() if expansions else q_raw
    q_tokens = tokenize(expanded_query)
    if not q_tokens:
        return 0.0

    title = str(lesson.get("title") or "")
    content = str(lesson.get("content") or lesson.get("snippet") or "")
    prevention = str(lesson.get("prevention") or "")
    tags = " ".join(str(t) for t in (lesson.get("tags") or []))
    lid = str(lesson.get("id") or "").lower().replace("-", "_")
    id_text = lid.replace("_", " ")
    blob = f"{title}\n{content}\n{prevention}\n{tags}\n{id_text}".lower()
    doc_tokens = set(tokenize(blob))
    title_l = title.lower()

    score = 0.0
    hits = sum(1 for t in q_tokens if _token_match(t, doc_tokens, blob))
    score += min(hits * 0.09, 0.54)

    # Title / prevention exact-ish boosts
    title_hits = sum(1 for t in q_tokens if _token_match(t, set(tokenize(title_l)), title_l))
    score += min(title_hits * 0.08, 0.32)
    prev_hits = sum(1 for t in q_tokens if t in prevention.lower())
    score += min(prev_hits * 0.05, 0.2)

    # Exact multi-word phrase bonuses (strong precision signal)
    q_lower = q_raw.lower()
    for phrase in (
        "close position",
        "iron condor",
        "position sizing",
        "win rate",
        "entry signals",
        "rag webhook",
        "tax optimization",
        "financial independence",
        "close_position",
        "api bug",
        "position accumulation",
        "aggregate position",
        "position management",
        "lancedb",
    ):
        if phrase in q_lower and phrase in blob:
            score += 0.18

    # Distinctive multi-word title/id alignment (bounded, linear scan — no ReDoS)
    tokens = [t for t in re.split(r"[^a-z0-9]+", q_lower) if t]
    for width in (2, 3, 4):
        if len(tokens) < width:
            continue
        for i in range(len(tokens) - width + 1):
            phrase_parts = tokens[i : i + width]
            phrase = " ".join(phrase_parts)
            compact = "_".join(phrase_parts)
            if len(compact) >= 6 and (compact in lid or phrase in title_l or phrase in blob[:2000]):
                score += 0.12

    # Intent / failure-mode boosts (precision for operator queries)
    if "error" in q_lower or "bug" in q_lower:
        for kw in ("bug", "error", "violation", "accumulation", "bypass", "hardcoded"):
            if kw in lid or kw in title_l:
                score += 0.14
    if "exit" in q_lower and (
        "management" in lid or "management" in title_l or "71k" in lid or "adjustment" in lid
    ):
        score += 0.22
    if "sizing" in q_lower and any(
        t in lid
        for t in (
            "accumulation",
            "aggregate",
            "5pct",
            "position_limit",
            "sizing",
            "hardcoded",
            "violation",
        )
    ):
        score += 0.24
    if "sofi" in q_lower and "sofi" in lid:
        score += 0.28
    if "webhook" in q_lower or ("rag" in q_lower and "query" in q_lower):
        if any(t in lid for t in ("webhook", "lancedb", "rag_failure", "rag_query", "rag")):
            score += 0.22
    if "roadmap" in q_lower or "independence" in q_lower:
        if any(t in lid for t in ("roadmap", "independence", "north_star", "wealth")):
            score += 0.2

    score += _severity_boost(str(lesson.get("severity") or ""))
    score += _recency_boost(lesson)

    # Lesson id / filename token boost (e.g. close_position, sofi, lot, alpaca)
    id_tokens = set(tokenize(id_text))
    id_hits = sum(1 for t in q_tokens if _token_match(t, id_tokens, lid))
    score += min(id_hits * 0.12, 0.4)

    # Trading-anchor overlap: rewards in-domain docs for in-domain queries
    q_anchors = {t for t in q_tokens if t in TRADING_ANCHOR_TOKENS}
    d_anchors = {t for t in doc_tokens if t in TRADING_ANCHOR_TOKENS}
    if q_anchors:
        score += min(len(q_anchors & d_anchors) / max(len(q_anchors), 1) * 0.25, 0.25)

    if score > 0:
        bj = bigram_jaccard(text_bigrams(expanded_query), text_bigrams(blob[:4000]))
        score += bj * 0.3

    return min(score, 1.8)


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
        variants.append("trading failure prevention " + " ".join(dict.fromkeys(focused_terms)))
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
            if s > 0.05:
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
