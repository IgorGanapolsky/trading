"""Single defended retrieve-for-trade contract.

Pipeline:
  capture 👎 → quality-gate → SQLite FTS5 store  (see feedback_quality + lesson_store)
  → retrieve: FTS5 seed + pragmatic hybrid (bigram-Jaccard + keyword)
  → multi-query: ≤3 variants when top lexical < 0.6
  → rerank: pairwise heuristic (+ optional LLM listwise)
  → assemble context → caller gates the next trade/tool deterministically
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.rag.cross_encoder_rerank import rerank_candidates
from src.rag.lesson_store import connect, ensure_index, search_fts
from src.rag.pragmatic_hybrid import (
    build_query_variants,
    pragmatic_hybrid_search,
    probe_top_lexical,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REWRITE_BELOW = 0.6
KNOWLEDGE_DIR = ROOT / "rag_knowledge" / "lessons_learned"


@dataclass
class RetrieveResult:
    lessons: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def critical_for_ticker(self, ticker: str) -> list[dict[str, Any]]:
        t = (ticker or "").upper()
        out = []
        for lesson in self.lessons:
            if str(lesson.get("severity", "")).upper() != "CRITICAL":
                continue
            blob = (
                f"{lesson.get('id', '')} {lesson.get('title', '')} "
                f"{lesson.get('content', '')} {lesson.get('snippet', '')}"
            ).upper()
            if t and t in blob:
                out.append(lesson)
        return out


def _load_markdown_corpus(knowledge_dir: Path | None = None) -> list[dict[str, Any]]:
    directory = Path(knowledge_dir or KNOWLEDGE_DIR)
    docs: list[dict[str, Any]] = []
    if not directory.exists():
        return docs
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue
        sev = "MEDIUM"
        m = re.search(
            r"severity\s*:\s*(critical|high|medium|low)",
            text,
            re.IGNORECASE,
        )
        if m:
            sev = m.group(1).upper()
        title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else path.stem
        prev_m = re.search(
            r"##\s*(?:prevention|how to avoid|solution)[^\n]*\n(.*?)(?=\n##|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        prevention = prev_m.group(1).strip() if prev_m else ""
        docs.append(
            {
                "id": path.stem,
                "title": title,
                "content": text,
                "snippet": text[:500],
                "severity": sev,
                "prevention": prevention,
                "tags": [],
                "file": str(path),
            }
        )
    return docs


def _merge_corpus(
    markdown_docs: list[dict[str, Any]],
    fts_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for doc in markdown_docs:
        by_id[str(doc["id"])] = doc
    for doc in fts_docs:
        did = str(doc["id"])
        if did in by_id:
            merged = {**by_id[did], **doc}
            # Prefer full markdown content when FTS row is shorter
            if len(str(by_id[did].get("content") or "")) > len(str(doc.get("content") or "")):
                merged["content"] = by_id[did]["content"]
            by_id[did] = merged
        else:
            by_id[did] = doc
    return list(by_id.values())


def resolve_query_plan(
    query: str,
    top_lexical: float,
    *,
    rewrite_below: float = DEFAULT_REWRITE_BELOW,
    query_rewrite: bool = True,
) -> dict[str, Any]:
    if not query_rewrite or top_lexical >= rewrite_below:
        return {
            "variants": [query],
            "rewrite_applied": False,
            "strategy": "original-only-strong-lexical"
            if top_lexical >= rewrite_below
            else "original-only",
            "rewrite_below": rewrite_below,
            "top_lexical": top_lexical,
        }
    variants = build_query_variants(query, max_variants=3)
    return {
        "variants": variants,
        "rewrite_applied": len(variants) > 1,
        "strategy": "deterministic-multi-query",
        "rewrite_below": rewrite_below,
        "top_lexical": top_lexical,
    }


def retrieve_for_trade(
    query: str,
    *,
    top_k: int = 5,
    candidate_pool: int = 40,
    severity_filter: str | None = None,
    rewrite_below: float = DEFAULT_REWRITE_BELOW,
    use_llm_rerank: bool | None = None,
    db_path: Path | None = None,
    knowledge_dir: Path | None = None,
    ensure_fts: bool = True,
) -> RetrieveResult:
    """Run the full defended retrieve path for a trade/agent query."""
    started_meta: dict[str, Any] = {"query": query, "top_k": top_k}

    if ensure_fts and os.environ.get("TRADING_RAG_SKIP_FTS_ENSURE", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        try:
            ensure_index(db_path, knowledge_dir)
        except Exception as exc:
            logger.warning("FTS ensure_index failed: %s", exc)
            started_meta["fts_ensure_error"] = str(exc)

    markdown_docs = _load_markdown_corpus(knowledge_dir)
    fts_docs: list[dict[str, Any]] = []
    fts_ids: list[str] = []
    try:
        conn = connect(db_path)
        try:
            fts_docs = search_fts(
                conn,
                query,
                limit=candidate_pool,
                severity=severity_filter,
            )
            fts_ids = [str(d["id"]) for d in fts_docs]
        finally:
            conn.close()
        started_meta["fts"] = {"applied": True, "hits": len(fts_docs)}
    except Exception as exc:
        logger.warning("FTS search unavailable: %s", exc)
        started_meta["fts"] = {"applied": False, "error": str(exc)}

    corpus = _merge_corpus(markdown_docs, fts_docs)
    if severity_filter:
        corpus = [
            d for d in corpus if str(d.get("severity", "")).upper() == severity_filter.upper()
        ]

    if not corpus:
        return RetrieveResult(lessons=[], meta={**started_meta, "strategy": "empty-corpus"})

    top_lex = probe_top_lexical(corpus, query)
    plan = resolve_query_plan(query, top_lex, rewrite_below=rewrite_below)
    hybrid = pragmatic_hybrid_search(
        corpus,
        query,
        fts_ranked_ids=fts_ids or None,
        query_variants=plan["variants"],
        top_k=candidate_pool,
        pool=candidate_pool,
    )
    candidates = hybrid["results"]
    # Domain phrase + severity boost (shared with QualityRetriever)
    try:
        from src.rag.retrieval_quality import domain_relevance_boost

        for row in candidates:
            blob = f"{row.get('title', '')} {row.get('snippet', '')} {row.get('content', '')}"
            boost = domain_relevance_boost(
                query,
                str(row.get("title") or ""),
                blob,
                str(row.get("severity") or ""),
            )
            base = float(row.get("score") or row.get("combinedScore") or 0.0)
            row["score"] = base + boost
            row["domainBoost"] = boost
        candidates.sort(key=lambda r: float(r.get("score") or 0.0), reverse=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("domain boost skipped: %s", exc)

    reranked = rerank_candidates(
        query,
        candidates,
        top_k=top_k,
        use_llm=use_llm_rerank,
    )

    # Normalize shape for TradeGateway / evaluators
    lessons: list[dict[str, Any]] = []
    for row in reranked:
        lessons.append(
            {
                "id": row.get("id"),
                "title": row.get("title") or row.get("id"),
                "severity": row.get("severity") or "MEDIUM",
                "score": float(row.get("score") or 0.0),
                "snippet": (row.get("snippet") or row.get("content") or "")[:500],
                "content": row.get("content") or row.get("snippet") or "",
                "prevention": row.get("prevention") or "",
                "tags": row.get("tags") or [],
                "file": row.get("file") or row.get("source_path") or "",
                "combinedScore": row.get("combinedScore"),
                "pairwiseHeuristicScore": row.get("pairwiseHeuristicScore"),
                "reranker": row.get("reranker"),
                "backend": "retrieve-for-trade",
            }
        )

    meta = {
        **started_meta,
        **plan,
        "hybrid": hybrid.get("meta") or {},
        "rerank_stages": (lessons[0].get("reranker") or {}).get("stages")
        if lessons
        else ["first-stage", "pairwise-heuristic"],
        "corpus_size": len(corpus),
        "top_lexical": top_lex,
    }
    return RetrieveResult(lessons=lessons, meta=meta)


def assemble_trade_context(
    lessons: list[dict[str, Any]],
    *,
    meta: dict[str, Any] | None = None,
    action: str = "",
) -> str:
    """Format retrieved lessons for injection into prompts / pre-trade checks."""
    lines = [
        "=== Trading RAG defended retrieval ===",
        "Review these prior lessons before proceeding:",
    ]
    if action:
        lines.append(f"Action: {action[:200]}")
    for i, lesson in enumerate(lessons, 1):
        text = (
            lesson.get("prevention")
            or lesson.get("snippet")
            or lesson.get("content")
            or lesson.get("title")
            or ""
        )
        text = re.sub(r"\s+", " ", str(text)).strip()[:280]
        sev = lesson.get("severity", "?")
        score = lesson.get("score")
        score_bit = f" score={float(score):.2f}" if score is not None else ""
        stages = (lesson.get("reranker") or {}).get("stages") or []
        stage_bit = f" via={'+'.join(stages)}" if stages else ""
        lines.append(f"{i}. [{sev}] {lesson.get('id')}{score_bit}{stage_bit}: {text}")
    if meta:
        if meta.get("rewrite_applied"):
            lines.append(
                f"(multi-query used: top_lexical={meta.get('top_lexical', 0):.2f} "
                f"< {meta.get('rewrite_below', DEFAULT_REWRITE_BELOW)})"
            )
        fts = meta.get("fts") or {}
        if fts.get("applied"):
            lines.append(f"(FTS5 seed hits={fts.get('hits', 0)})")
    return "\n".join(lines)


def capture_and_store_feedback(
    *,
    signal: str,
    context: str = "",
    what_went_wrong: str = "",
    what_to_change: str = "",
    what_worked: str = "",
    tags: list[str] | None = None,
    db_path: Path | None = None,
    also_write_markdown: bool = True,
) -> dict[str, Any]:
    """Capture 👎/👍 → quality-gate → FTS5 (+ optional markdown lesson)."""
    from src.rag.feedback_quality import assess_promotion_quality, build_lesson_payload
    from src.rag.lesson_store import upsert_feedback_lesson

    decision = assess_promotion_quality(
        signal=signal,
        context=context,
        what_went_wrong=what_went_wrong,
        what_to_change=what_to_change,
        what_worked=what_worked,
    )
    if not decision.promotable:
        return {
            "accepted": True,
            "promoted": False,
            "status": "rejected",
            "quality_gate": decision.quality_gate,
            "reason": decision.reason,
        }

    payload = build_lesson_payload(
        signal=signal,
        context=context,
        what_went_wrong=what_went_wrong,
        what_to_change=what_to_change,
        what_worked=what_worked,
        tags=tags,
    )
    if payload is None:
        return {
            "accepted": True,
            "promoted": False,
            "status": "rejected",
            "quality_gate": decision.quality_gate,
            "reason": decision.reason,
        }
    import hashlib
    from datetime import UTC, datetime

    digest = hashlib.sha256(payload["content"].encode("utf-8")).hexdigest()[:10]
    day = datetime.now(UTC).strftime("%Y%m%d")
    lesson_id = f"fb_{decision.signal[:3]}_{day}_{digest}"

    conn = connect(db_path)
    try:
        upsert_feedback_lesson(
            conn,
            lesson_id=lesson_id,
            title=payload["title"],
            content=payload["content"],
            severity=payload["severity"],
            prevention=payload["prevention"],
            tags=payload["tags"],
        )
    finally:
        conn.close()

    md_path = None
    if also_write_markdown:
        knowledge = KNOWLEDGE_DIR
        knowledge.mkdir(parents=True, exist_ok=True)
        md_path = knowledge / f"{lesson_id}.md"
        md_path.write_text(
            f"# {payload['title']}\n\n"
            f"**Severity**: {payload['severity']}\n\n"
            f"{payload['content']}\n\n"
            f"## Prevention\n\n{payload['prevention']}\n\n"
            f"## Tags\n\n" + ", ".join(f"`{t}`" for t in payload["tags"]) + "\n",
            encoding="utf-8",
        )

    return {
        "accepted": True,
        "promoted": True,
        "status": "promoted",
        "lesson_id": lesson_id,
        "quality_gate": decision.quality_gate,
        "markdown_path": str(md_path) if md_path else None,
    }
