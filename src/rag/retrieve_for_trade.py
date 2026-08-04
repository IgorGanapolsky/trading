"""Single defended retrieve-for-trade contract.

Pipeline:
  capture 👎 → quality-gate → SQLite FTS5 store  (see feedback_quality + lesson_store)
  → retrieve: FTS5 seed + pragmatic hybrid (bigram-Jaccard + keyword)
  → multi-query: ≤3 variants when top lexical < 0.6
  → rerank: pairwise heuristic (+ optional LLM listwise)
  → ACL filter (principal / sensitivity)
  → assemble context → caller gates the next trade/tool deterministically
  → emit retrieval trace (observability)
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.rag.acl import Principal, filter_documents, infer_sensitivity
from src.rag.cross_encoder_rerank import rerank_candidates
from src.rag.lesson_store import connect, ensure_index, search_fts
from src.rag.observability import (
    emit_trace,
    estimate_tokens,
    finish_trace,
    new_trace,
)
from src.rag.pragmatic_hybrid import (
    build_query_variants,
    pragmatic_hybrid_search,
    probe_top_lexical,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REWRITE_BELOW = 0.6
KNOWLEDGE_DIR = ROOT / "rag_knowledge" / "lessons_learned"
# Below this top score, treat as OOD / unanswerable for trade gates.
DEFAULT_OOD_MIN_SCORE = float(os.getenv("TRADING_RAG_OOD_MIN_SCORE", "0.08"))


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


_FAMILY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "spy_put_credit",
        re.compile(
            r"put[\s_-]?credit|bull[\s_-]?put|pcs_|spy_put_credit|short put spread",
            re.I,
        ),
    ),
    (
        "iron_condor",
        re.compile(r"iron[\s_-]?condor|\bic\b|ic_simple|4[\s-]?leg", re.I),
    ),
]


def _infer_strategy_family(text: str, path_stem: str = "") -> str:
    blob = f"{path_stem} {text[:2000]}"
    for family, pat in _FAMILY_PATTERNS:
        if pat.search(blob):
            return family
    return "general"


def _extract_section_pack(full_text: str, prevention: str) -> str:
    """Parent expand: prefer Prevention + What Happened for trade gates."""
    parts: list[str] = []
    for header in (
        r"##\s*(?:prevention|how to avoid|solution)[^\n]*\n(.*?)(?=\n##|\Z)",
        r"##\s*(?:what happened|incident|problem)[^\n]*\n(.*?)(?=\n##|\Z)",
    ):
        m = re.search(header, full_text, re.I | re.DOTALL)
        if m and m.group(1).strip():
            parts.append(m.group(1).strip()[:1200])
    if parts:
        return "\n\n".join(parts)
    if prevention:
        return prevention[:1500]
    return full_text[:1500]


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
        tags: list[str] = []
        tags_m = re.search(r"##\s*Tags\s*\n(.+?)(?=\n##|\Z)", text, re.I | re.DOTALL)
        if tags_m:
            tags = re.findall(r"`([^`]+)`", tags_m.group(1))
        family = _infer_strategy_family(text, path.stem)
        docs.append(
            {
                "id": path.stem,
                "title": title,
                "content": text,
                "snippet": text[:500],
                "severity": sev,
                "prevention": prevention,
                "section_pack": _extract_section_pack(text, prevention),
                "tags": tags,
                "file": str(path),
                "doc_type": "lesson",
                "strategy_family": family,
                "section_type": "prevention" if prevention else "content",
                "parent_id": path.stem,
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


def _apply_metadata_filters(
    corpus: list[dict[str, Any]],
    *,
    severity_filter: str | None,
    strategy_family: str | None,
    doc_type: str | None = "lesson",
) -> list[dict[str, Any]]:
    """Hard metadata filters. Soft-include general when family filter is set."""
    out = corpus
    if severity_filter:
        want = severity_filter.upper()
        out = [d for d in out if str(d.get("severity", "")).upper() == want]
    if doc_type:
        typed = [d for d in out if str(d.get("doc_type", "lesson")) == doc_type]
        if typed:
            out = typed
    if strategy_family:
        fam = strategy_family.lower().strip()
        if fam and fam not in {"*", "all", "any"}:
            filtered = [
                d
                for d in out
                if str(d.get("strategy_family", "general")).lower() in {fam, "general"}
            ]
            # Never empty the corpus solely due to family — fall back unfiltered family
            if filtered:
                out = filtered
    return out


def _parent_expand_lessons(
    rows: list[dict[str, Any]],
    corpus_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand matched rows to parent prevention pack when available."""
    expanded: list[dict[str, Any]] = []
    for row in rows:
        lid = str(row.get("id") or "")
        parent = corpus_by_id.get(lid) or corpus_by_id.get(str(row.get("parent_id") or ""))
        pack = ""
        if parent:
            pack = str(parent.get("section_pack") or parent.get("prevention") or "")
        content = pack or row.get("content") or row.get("snippet") or ""
        prevention = (parent or {}).get("prevention") or row.get("prevention") or ""
        expanded.append(
            {
                **row,
                "content": content,
                "prevention": prevention,
                "snippet": str(content)[:500],
                "section_pack": pack,
                "parent_expanded": bool(pack),
                "strategy_family": (parent or row).get("strategy_family", "general"),
                "doc_type": (parent or row).get("doc_type", "lesson"),
            }
        )
    return expanded


def retrieve_for_trade(
    query: str,
    *,
    top_k: int = 5,
    candidate_pool: int = 40,
    severity_filter: str | None = None,
    strategy_family: str | None = None,
    doc_type: str | None = "lesson",
    rewrite_below: float = DEFAULT_REWRITE_BELOW,
    use_llm_rerank: bool | None = None,
    db_path: Path | None = None,
    knowledge_dir: Path | None = None,
    ensure_fts: bool = True,
    parent_expand: bool = True,
    principal: Principal | None = None,
    ood_min_score: float = DEFAULT_OOD_MIN_SCORE,
    emit_retrieval_trace: bool = True,
) -> RetrieveResult:
    """Run the full defended retrieve path for a trade/agent query.

    Stages: FTS seed → metadata filters → pragmatic hybrid (BM25-ish + bigram)
    → multi-query when weak → heuristic/CE rerank → optional parent expand
    → ACL filter → OOD hard-reject → retrieval trace.
    """
    t0 = time.perf_counter()
    principal = principal or Principal.operator()
    trace = new_trace(query, principal=principal.name)
    started_meta: dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "strategy_family": strategy_family,
        "severity_filter": severity_filter,
        "doc_type": doc_type,
        "principal": principal.name,
        "trace_id": trace.trace_id,
    }

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
    # Infer family on FTS-only rows
    for d in corpus:
        if not d.get("strategy_family"):
            d["strategy_family"] = _infer_strategy_family(
                str(d.get("content") or d.get("title") or ""),
                str(d.get("id") or ""),
            )
        if not d.get("doc_type"):
            d["doc_type"] = "lesson"
        if not d.get("section_pack") and d.get("content"):
            d["section_pack"] = _extract_section_pack(
                str(d.get("content") or ""),
                str(d.get("prevention") or ""),
            )

    corpus = _apply_metadata_filters(
        corpus,
        severity_filter=severity_filter,
        strategy_family=strategy_family,
        doc_type=doc_type,
    )
    started_meta["corpus_after_filters"] = len(corpus)

    if not corpus:
        meta = {**started_meta, "strategy": "empty-corpus", "ood_rejected": False}
        if emit_retrieval_trace:
            trace.strategy = "empty-corpus"
            finish_trace(trace, t0=t0)
            emit_trace(trace)
        return RetrieveResult(lessons=[], meta=meta)

    corpus_by_id = {str(d["id"]): d for d in corpus}

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
    reranked = rerank_candidates(
        query,
        candidates,
        top_k=max(top_k * 2, top_k),  # extra headroom for ACL drops
        use_llm=use_llm_rerank,
    )
    if parent_expand:
        reranked = _parent_expand_lessons(reranked, corpus_by_id)

    # Normalize shape for TradeGateway / evaluators + attach ACL sensitivity
    lessons: list[dict[str, Any]] = []
    for row in reranked:
        severity = row.get("severity") or "MEDIUM"
        tags = row.get("tags") or []
        content = row.get("content") or row.get("snippet") or ""
        sensitivity = row.get("sensitivity") or infer_sensitivity(
            severity=str(severity),
            tags=tags,
            text=f"{row.get('title') or ''} {content}"[:600],
        )
        sens_value = sensitivity.value if hasattr(sensitivity, "value") else str(sensitivity)
        lessons.append(
            {
                "id": row.get("id"),
                "title": row.get("title") or row.get("id"),
                "severity": severity,
                "score": float(row.get("score") or 0.0),
                "snippet": (row.get("snippet") or row.get("content") or "")[:500],
                "content": content,
                "prevention": row.get("prevention") or "",
                "section_pack": row.get("section_pack") or "",
                "tags": tags,
                "file": row.get("file") or row.get("source_path") or "",
                "strategy_family": row.get("strategy_family") or "general",
                "doc_type": row.get("doc_type") or "lesson",
                "parent_expanded": bool(row.get("parent_expanded")),
                "sensitivity": sens_value,
                "combinedScore": row.get("combinedScore"),
                "pairwiseHeuristicScore": row.get("pairwiseHeuristicScore"),
                "reranker": row.get("reranker"),
                "backend": "retrieve-for-trade",
            }
        )

    pre_acl = len(lessons)
    lessons = filter_documents(lessons, principal)
    acl_dropped = pre_acl - len(lessons)
    lessons = lessons[:top_k]

    # OOD hard-reject: empty result when top score is noise-level
    top_score = float(lessons[0]["score"]) if lessons else 0.0
    ood_rejected = bool(lessons) and top_score < ood_min_score
    if ood_rejected:
        lessons = []

    path_bits = ["fts", "hybrid", "rerank"]
    if parent_expand:
        path_bits.append("parent_expand")
    path_bits.append("acl")
    if ood_rejected:
        path_bits.append("ood_reject")

    meta = {
        **started_meta,
        **plan,
        "hybrid": hybrid.get("meta") or {},
        "rerank_stages": (lessons[0].get("reranker") or {}).get("stages")
        if lessons
        else ["first-stage", "pairwise-heuristic"],
        "corpus_size": len(corpus),
        "top_lexical": top_lex,
        "parent_expand": parent_expand,
        "acl_dropped": acl_dropped,
        "ood_rejected": ood_rejected,
        "ood_min_score": ood_min_score,
        "top_score": top_score,
        "path": "+".join(path_bits),
    }

    if emit_retrieval_trace:
        trace.strategy = meta["path"]
        trace.stages = path_bits
        trace.fts_hits = int((started_meta.get("fts") or {}).get("hits") or 0)
        trace.hybrid_pool = len(candidates)
        trace.variants = list(plan.get("variants") or [query])
        trace.top_scores = [float(x.get("score") or 0) for x in lessons[:5]]
        trace.top_ids = [str(x.get("id") or "") for x in lessons[:5]]
        trace.acl_dropped = acl_dropped
        trace.token_estimate = estimate_tokens(
            " ".join(str(x.get("snippet") or "") for x in lessons)
        )
        finish_trace(trace, t0=t0)
        emit_trace(trace)
        meta["latency_ms"] = trace.latency_ms

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
            lesson.get("section_pack")
            or lesson.get("prevention")
            or lesson.get("snippet")
            or lesson.get("content")
            or lesson.get("title")
            or ""
        )
        text = re.sub(r"\s+", " ", str(text)).strip()[:280]
        sev = lesson.get("severity", "?")
        fam = lesson.get("strategy_family") or "general"
        score = lesson.get("score")
        score_bit = f" score={float(score):.2f}" if score is not None else ""
        stages = (lesson.get("reranker") or {}).get("stages") or []
        stage_bit = f" via={'+'.join(stages)}" if stages else ""
        expand_bit = " parent+" if lesson.get("parent_expanded") else ""
        lines.append(
            f"{i}. [{sev}|{fam}] {lesson.get('id')}{score_bit}{stage_bit}{expand_bit}: {text}"
        )
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
