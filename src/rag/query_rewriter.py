"""RAG Query Rewriter & Synonym Expansion Engine.

Expands short agentic trading queries into domain-enriched search queries
to boost vector and BM25 retrieval recall for risk rules and strategy lessons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "put credit": ["short put spread", "credit spread", "put spread", "15 delta", "45 dte"],
    "iron condor": ["4-leg spread", "short strangle defined risk", "50% profit target", "7 dte exit"],
    "circuit breaker": ["drawdown kill switch", "5% account protection", "trading halt"],
    "bogleheads": ["three fund portfolio", "bogleheads forum", "long term buy and hold"],
    "section 1256": ["xsp", "spx", "60/40 tax treatment", "index options"],
}


@dataclass(frozen=True)
class ExpandedQuery:
    original_query: str
    expanded_query: str
    synonyms_added: tuple[str, ...]


class RAGQueryRewriter:
    """Rewrites and expands queries with domain-specific trading terms."""

    def rewrite(self, query: str) -> ExpandedQuery:
        q_lower = query.lower().strip()
        added: list[str] = []

        for key, terms in DOMAIN_SYNONYMS.items():
            if key in q_lower:
                for t in terms:
                    if t not in q_lower:
                        added.append(t)

        if added:
            expanded = f"{query} " + " ".join(added[:4])
        else:
            expanded = query

        return ExpandedQuery(
            original_query=query,
            expanded_query=expanded.strip(),
            synonyms_added=tuple(added[:4]),
        )
