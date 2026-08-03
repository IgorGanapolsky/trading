"""Production retrieval quality stack for trading lessons.

Ranks levers (this repo):
  1. Hybrid BM25/FTS + dense (when available) with RRF
  2. Cross-encoder / domain rerank
  3. Query rewrite + multi-query
  4. Parent-child (match small chunk → return full lesson)
  5. Metadata filters (severity, strategy, ticker)
  6. Header-aware chunking + richer metadata on index
  7. Better embeddings (optional BGE) — never block import

Wire: ``QualityRetriever.retrieve()`` used by TradingRAGPipeline when enabled.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

TICKER_RE = re.compile(
    r"\b(SPY|XSP|SPX|QQQ|IWM|SOFI|AAPL|MSFT|NVDA|TSLA|VOO|AMZN|META|GOOG|AMD)\b",
    re.IGNORECASE,
)
HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
SEVERITY_RE = re.compile(
    r"\*\*severity\*\*:\s*\*?(critical|high|medium|low|p0|p1|p2|p3)\*?",
    re.IGNORECASE,
)

STRATEGY_TAGS = {
    "put_credit": ("put credit", "bull put", "credit spread", "spy_put_credit"),
    "iron_condor": ("iron condor", "ic simple", "ic_simple", "4-leg"),
    "risk": ("stop loss", "kill switch", "drawdown", "position siz"),
    "tax": ("section 1256", "wash sale", "1256"),
    "ops": ("inventory", "broker", "alpaca", "ci ", "github"),
}


@dataclass
class ChunkMeta:
    parent_id: str
    chunk_id: str
    title: str
    severity: str
    strategy_family: str
    tickers: list[str]
    tags: list[str]
    section: str
    text: str


@dataclass
class RetrievalHit:
    lesson_id: str
    title: str
    severity: str
    snippet: str
    score: float
    source: str  # fts|vector|hybrid|parent
    metadata: dict[str, Any] = field(default_factory=dict)


def extract_severity(text: str) -> str:
    m = SEVERITY_RE.search(text or "")
    if not m:
        return "LOW"
    raw = m.group(1).upper()
    return {"P0": "CRITICAL", "P1": "HIGH", "P2": "MEDIUM", "P3": "LOW"}.get(raw, raw)


def extract_tickers(text: str) -> list[str]:
    return list(dict.fromkeys(t.upper() for t in TICKER_RE.findall(text or "")))


def extract_strategy_family(text: str) -> str:
    low = (text or "").lower()
    for fam, keys in STRATEGY_TAGS.items():
        if any(k in low for k in keys):
            return fam
    return "general"


def header_aware_chunks(
    parent_id: str,
    title: str,
    content: str,
    *,
    max_chars: int = 900,
    overlap: int = 120,
) -> list[ChunkMeta]:
    """Split on markdown headers; pack sections into ≤max_chars with light overlap."""
    text = content or ""
    severity = extract_severity(text)
    strategy = extract_strategy_family(text)
    tickers = extract_tickers(text)
    tags = [strategy] + tickers[:5]

    # Split into sections by headers
    parts: list[tuple[str, str]] = []
    matches = list(HEADER_RE.finditer(text))
    if not matches:
        parts.append((title, text))
    else:
        if matches[0].start() > 0:
            parts.append((title, text[: matches[0].start()].strip()))
        for i, m in enumerate(matches):
            sec_title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            parts.append((sec_title, body))

    chunks: list[ChunkMeta] = []
    idx = 0
    for sec_title, body in parts:
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append(
                ChunkMeta(
                    parent_id=parent_id,
                    chunk_id=f"{parent_id}#c{idx}",
                    title=title,
                    severity=severity,
                    strategy_family=strategy,
                    tickers=tickers,
                    tags=tags,
                    section=sec_title,
                    text=body,
                )
            )
            idx += 1
            continue
        # pack long sections
        start = 0
        while start < len(body):
            end = min(len(body), start + max_chars)
            piece = body[start:end]
            chunks.append(
                ChunkMeta(
                    parent_id=parent_id,
                    chunk_id=f"{parent_id}#c{idx}",
                    title=title,
                    severity=severity,
                    strategy_family=strategy,
                    tickers=tickers,
                    tags=tags,
                    section=sec_title,
                    text=piece,
                )
            )
            idx += 1
            if end >= len(body):
                break
            start = max(0, end - overlap)
    return chunks


def apply_metadata_filters(
    hits: list[dict[str, Any]],
    *,
    min_severity: str | None = None,
    strategy_family: str | None = None,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter candidate rows by structured metadata (fail-open if field missing)."""
    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "": 0}
    min_rank = sev_rank.get((min_severity or "").upper(), 0)
    out: list[dict[str, Any]] = []
    want_tickers = {t.upper() for t in (tickers or [])}
    for h in hits:
        sev = str(h.get("severity") or "").upper()
        if min_rank and sev_rank.get(sev, 0) < min_rank:
            continue
        fam = str(h.get("strategy_family") or h.get("family") or "")
        if strategy_family and fam and fam != strategy_family:
            continue
        if want_tickers:
            row_t = {str(x).upper() for x in (h.get("tickers") or [])}
            # Also allow ticker mention in text
            blob = (str(h.get("content") or "") + " " + str(h.get("snippet") or "")).upper()
            if not (want_tickers & row_t) and not any(t in blob for t in want_tickers):
                continue
        out.append(h)
    return out


def rrf_fuse(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    k: float = 60.0,
    id_key: str = "id",
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion across multiple ranked result lists."""
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    for results in ranked_lists:
        for rank, item in enumerate(results, 1):
            lid = str(item.get(id_key) or item.get("lesson_id") or f"row_{rank}")
            scores[lid] = scores.get(lid, 0.0) + 1.0 / (k + rank)
            if lid not in items:
                items[lid] = dict(item)
            items[lid]["rrf_score"] = scores[lid]
    ordered = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
    return [items[i] for i in ordered]


# Trading safety phrases: big boost when query and doc share these
_SAFETY_PHRASES: tuple[str, ...] = (
    "stop loss",
    "200%",
    "put credit",
    "iron condor",
    "unclean inventory",
    "inventory",
    "kill switch",
    "live blocked",
    "1-lot",
    "7 dte",
    "profit target",
    "section 1256",
    "wash sale",
    "orphan",
    "freehand",
)


def domain_relevance_boost(query: str, title: str, content: str, severity: str) -> float:
    """Additive boost for phrase overlap + severity alignment with risk queries."""
    q = (query or "").lower()
    blob = f"{title} {content}".lower()
    boost = 0.0
    for phrase in _SAFETY_PHRASES:
        if phrase in q and phrase in blob:
            boost += 0.35
        elif phrase in q and any(w in blob for w in phrase.split() if len(w) > 3):
            boost += 0.08
    # Risk-flavored queries prefer CRITICAL/HIGH
    riskish = any(
        w in q
        for w in (
            "stop",
            "loss",
            "kill",
            "halt",
            "block",
            "inventory",
            "unclean",
            "fail",
            "critical",
        )
    )
    sev = (severity or "").upper()
    if riskish and sev == "CRITICAL":
        boost += 0.25
    elif riskish and sev == "HIGH":
        boost += 0.12
    # Penalize wealth/roadmap noise when query is operational risk
    if riskish and any(x in blob for x in ("wealth building", "roadmap", "north star 30")):
        boost -= 0.2
    return boost


class QualityRetriever:
    """Orchestrates rewrite → hybrid → filter → rerank → parent expand."""

    def __init__(self, pipeline: Any | None = None):
        self.pipeline = pipeline
        self._parent_store: dict[str, str] = {}
        self._parent_meta: dict[str, dict[str, Any]] = {}
        self._children: list[ChunkMeta] = []

    def index_parents(self, lessons: list[dict[str, Any]]) -> int:
        """Build parent store + header-aware children from lesson dicts."""
        self._parent_store.clear()
        self._parent_meta.clear()
        self._children.clear()
        for row in lessons:
            pid = str(row.get("lesson_id") or row.get("id") or "")
            if not pid:
                continue
            title = str(row.get("title") or pid)
            content = str(row.get("content") or "")
            self._parent_store[pid] = content
            sev = str(row.get("severity") or extract_severity(content)).upper()
            fam = extract_strategy_family(content)
            ticks = extract_tickers(content)
            self._parent_meta[pid] = {
                "title": title,
                "severity": sev,
                "strategy_family": fam,
                "tickers": ticks,
            }
            for ch in header_aware_chunks(pid, title, content):
                self._children.append(ch)
        return len(self._children)

    def _rewrite_queries(self, query: str) -> list[str]:
        qs = [query]
        try:
            from src.rag.query_rewriter import RAGQueryRewriter

            exp = RAGQueryRewriter().rewrite(query)
            if exp.expanded_query and exp.expanded_query != query:
                qs.append(exp.expanded_query)
        except Exception as exc:  # noqa: BLE001
            logger.debug("query rewrite skipped: %s", exc)
        # multi-query from pipeline helpers if present
        try:
            from src.rag.rag_pipeline import generate_query_variants

            for v in generate_query_variants(query, max_variants=3):
                text = getattr(v, "text", None) or str(v)
                if text and text not in qs:
                    qs.append(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("query variants skipped: %s", exc)
        return qs[:5]

    def _fts_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self.pipeline is None:
            return []
        try:
            raw = self.pipeline.query(query, top_k=top_k * 2, severity_filter=None)
            out = []
            for item in raw:
                lid = str(item.get("id"))
                meta = self._parent_meta.get(lid, {})
                out.append(
                    {
                        "id": lid,
                        "title": item.get("title") or meta.get("title", lid),
                        "severity": item.get("severity") or meta.get("severity", "LOW"),
                        "snippet": item.get("snippet", ""),
                        "content": item.get("content", ""),
                        "score": float(item.get("score") or 0.0),
                        "strategy_family": meta.get("strategy_family", "general"),
                        "tickers": meta.get("tickers", []),
                        "source": "fts",
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.debug("fts search failed: %s", exc)
            return []

    def _child_lexical(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Cheap lexical match over child chunks, then promote to parent ids."""
        if not self._children:
            return []
        q_tokens = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
        if not q_tokens:
            return []
        scored: list[tuple[float, ChunkMeta]] = []
        for ch in self._children:
            blob = f"{ch.section} {ch.text}".lower()
            hits = sum(1 for t in q_tokens if t in blob)
            if hits:
                scored.append((hits / max(len(q_tokens), 1), ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sc, ch in scored[: top_k * 3]:
            if ch.parent_id in seen:
                continue
            seen.add(ch.parent_id)
            meta = self._parent_meta.get(ch.parent_id, {})
            parent_body = self._parent_store.get(ch.parent_id, ch.text)
            out.append(
                {
                    "id": ch.parent_id,
                    "title": ch.title,
                    "severity": ch.severity or meta.get("severity", "LOW"),
                    "snippet": ch.text[:400],
                    "content": parent_body,  # parent-child expand
                    "score": float(sc),
                    "strategy_family": ch.strategy_family,
                    "tickers": ch.tickers,
                    "source": "parent_child",
                    "matched_chunk": ch.chunk_id,
                    "section": ch.section,
                }
            )
            if len(out) >= top_k:
                break
        return out

    def _vector_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Optional dense retrieval via TradeRAG / Lance path if installed."""
        try:
            from src.rag.vector_store import TradeRAG

            store = TradeRAG()
            # TradeRAG API varies; try query methods
            if hasattr(store, "query"):
                res = store.query(query, top_k=top_k)
            elif hasattr(store, "search"):
                res = store.search(query, top_k=top_k)
            else:
                return []
            out = []
            for i, item in enumerate(res or []):
                if isinstance(item, dict):
                    lid = str(item.get("id") or item.get("lesson_id") or f"v{i}")
                    out.append(
                        {
                            "id": lid,
                            "title": item.get("title", lid),
                            "severity": item.get("severity", "LOW"),
                            "snippet": str(item.get("snippet") or item.get("content") or "")[:400],
                            "content": item.get("content", ""),
                            "score": float(item.get("score") or 1.0 / (i + 1)),
                            "source": "vector",
                        }
                    )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.debug("vector search unavailable: %s", exc)
            return []

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        min_severity: str | None = None,
        strategy_family: str | None = None,
        tickers: list[str] | None = None,
        use_vector: bool = True,
        use_parent_child: bool = True,
        use_rerank: bool = True,
    ) -> list[RetrievalHit]:
        """Full quality stack. Degrades gracefully if optional deps missing."""
        queries = self._rewrite_queries(query)
        fts_lists: list[list[dict[str, Any]]] = []
        for q in queries:
            fts_lists.append(self._fts_search(q, top_k=top_k * 2))
        fts_merged = rrf_fuse(fts_lists, top_n=top_k * 4) if fts_lists else []

        lists: list[list[dict[str, Any]]] = [fts_merged]
        if use_parent_child:
            lists.append(self._child_lexical(query, top_k=top_k * 2))
        if use_vector:
            lists.append(self._vector_search(query, top_k=top_k * 2))

        fused = rrf_fuse([lst for lst in lists if lst], top_n=top_k * 4)

        # Auto metadata from query if not provided
        auto_tickers = tickers or extract_tickers(query)
        filtered = apply_metadata_filters(
            fused,
            min_severity=min_severity,
            strategy_family=strategy_family,
            tickers=auto_tickers or None,
        )
        # Fail-open: if filters wiped everything, keep fused
        candidates = filtered if filtered else fused

        # Domain phrase boost before rerank (fixes wealth-pillar false tops on risk queries)
        for c in candidates:
            blob = f"{c.get('title', '')} {c.get('snippet', '')} {c.get('content', '')}"
            boost = domain_relevance_boost(
                query, str(c.get("title", "")), blob, str(c.get("severity", ""))
            )
            c["score"] = float(c.get("score") or c.get("rrf_score") or 0.0) + boost
        candidates.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)

        if use_rerank and candidates:
            try:
                from src.rag.rag_reranker import RAGReranker

                # Prefer pipeline CE reranker if present
                if self.pipeline is not None and hasattr(self.pipeline, "_reranker"):
                    reranked = self.pipeline._reranker.rerank(
                        query, candidates, top_n=top_k * 2
                    )
                    if reranked and isinstance(reranked[0], dict):
                        candidates = reranked
                    else:
                        # RAGEReranker may return list[dict] with rerank_score
                        tmp = []
                        for r in reranked:
                            if isinstance(r, dict):
                                tmp.append(r)
                            else:
                                tmp.append(
                                    {
                                        "id": getattr(r, "lesson_id", ""),
                                        "title": getattr(r, "title", ""),
                                        "score": getattr(r, "reranked_score", 0.0),
                                        "snippet": getattr(r, "content_snippet", ""),
                                        "severity": "LOW",
                                    }
                                )
                        if tmp:
                            candidates = tmp
                else:
                    rr = RAGReranker().rerank(query, candidates, top_n=top_k * 2)
                    candidates = [
                        {
                            "id": r.lesson_id,
                            "title": r.title,
                            "score": r.reranked_score,
                            "snippet": r.content_snippet,
                            "severity": "LOW",
                            "source": "rerank",
                        }
                        for r in rr
                    ]
            except Exception as exc:  # noqa: BLE001
                logger.debug("rerank skipped: %s", exc)

        # Expand to parent full content when we only have chunk
        hits: list[RetrievalHit] = []
        seen: set[str] = set()
        for c in candidates:
            lid = str(c.get("id") or c.get("lesson_id") or "")
            if not lid or lid in seen:
                continue
            seen.add(lid)
            parent = self._parent_store.get(lid, "")
            meta = self._parent_meta.get(lid, {})
            snippet = str(c.get("snippet") or "")[:500]
            if parent and len(parent) > len(snippet):
                # prefer prevention-heavy slice if present
                low = parent.lower()
                if "## prevention" in low:
                    i = low.index("## prevention")
                    snippet = parent[i : i + 500]
                elif not snippet:
                    snippet = parent[:500]
            hits.append(
                RetrievalHit(
                    lesson_id=lid,
                    title=str(c.get("title") or meta.get("title") or lid),
                    severity=str(c.get("severity") or meta.get("severity") or "LOW").upper(),
                    snippet=snippet,
                    score=float(c.get("score") or c.get("rrf_score") or c.get("rerank_score") or 0.0),
                    source=str(c.get("source") or "hybrid"),
                    metadata={
                        "strategy_family": c.get("strategy_family") or meta.get("strategy_family"),
                        "tickers": c.get("tickers") or meta.get("tickers") or [],
                        "matched_chunk": c.get("matched_chunk"),
                        "section": c.get("section"),
                    },
                )
            )
            if len(hits) >= top_k:
                break
        return hits
