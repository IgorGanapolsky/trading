"""Report which retrieval tier is actually running.

The RAG stack degrades silently by design: BGE embeddings fall back to TF-IDF, the
cross-encoder reranker falls back to a heuristic, LanceDB falls back to keyword search.
That design is deliberate -- a search-index failure must never block trade execution
(Feb 10-13, 2026 outage).

Silent degradation is not the same as *invisible* degradation. Measured on the repo's
own golden set, the degraded tier scored precision@5 0.20 against 0.36 for the full
tier -- retrieval quality nearly halved with no alarm, and a release billed as an
improvement shipped as a measured regression, because nothing named the active tier.

This module names it. Callers decide whether to warn; nobody has to infer it.
"""

from __future__ import annotations

import importlib.util
from typing import Any

# Measured with scripts/evaluate_rag.py against the production retriever, 2026-08-04.
# Both rows were taken with lancedb ABSENT; the only variable was sentence-transformers.
# Labelling matters: attributing these numbers to "any optional dep missing" would blame
# lancedb for a gap it was never measured against.
MEASURED_WITH_CROSS_ENCODER = {"precision_at_5": 0.36, "recall_at_5": 0.575, "mrr": 0.725}
MEASURED_WITHOUT_CROSS_ENCODER = {"precision_at_5": 0.20, "recall_at_5": 0.3083, "mrr": 0.50}

# Missing this measurably halves retrieval quality -- it drives both the embedder and
# the reranker tier.
_QUALITY_CRITICAL_DEP = "sentence_transformers"
# Optional capability with no measured effect on the golden set. Reported, not alarmed.
_UNMEASURED_DEPS = ("sklearn", "lancedb")
_DEP_DISPLAY = {
    "sentence_transformers": "sentence-transformers",
    "sklearn": "scikit-learn",
    "lancedb": "lancedb",
}


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def describe_retrieval_tier() -> dict[str, Any]:
    """Return the active retrieval components and whether quality is degraded.

    `quality_degraded` keys ONLY on the dependency whose absence was actually measured
    to halve retrieval quality. Other absent optionals are listed under
    `unmeasured_absent` so they stay visible without implying a quality claim nobody
    measured.
    """
    has_critical = _installed(_QUALITY_CRITICAL_DEP)
    unmeasured_absent = [_DEP_DISPLAY[n] for n in _UNMEASURED_DEPS if not _installed(n)]

    return {
        "quality_degraded": not has_critical,
        "embedder": "BAAI/bge-base-en-v1.5" if has_critical else "tfidf-fallback",
        "reranker": "cross-encoder" if has_critical else "heuristic",
        "semantic_index": "lancedb" if _installed("lancedb") else "none(keyword-only)",
        "quality_critical_dep": _DEP_DISPLAY[_QUALITY_CRITICAL_DEP],
        "unmeasured_absent": unmeasured_absent,
        "remedy": "sync the declared [rag] extra into the venv",
        "measured_with_cross_encoder": MEASURED_WITH_CROSS_ENCODER,
        "measured_without_cross_encoder": MEASURED_WITHOUT_CROSS_ENCODER,
    }


def tier_summary_line() -> str:
    """One-line human summary suitable for a health check or log banner."""
    tier = describe_retrieval_tier()
    absent = tier["unmeasured_absent"]
    tail = f"; absent (no measured effect): {', '.join(absent)}" if absent else ""

    if not tier["quality_degraded"]:
        return (
            f"retrieval tier FULL (embedder={tier['embedder']}, reranker={tier['reranker']}){tail}"
        )

    good = tier["measured_with_cross_encoder"]["precision_at_5"]
    bad = tier["measured_without_cross_encoder"]["precision_at_5"]
    return (
        f"retrieval tier DEGRADED — missing {tier['quality_critical_dep']} "
        f"(embedder={tier['embedder']}, reranker={tier['reranker']}); "
        f"measured precision@5 {bad} vs {good} with the cross-encoder{tail}"
    )
