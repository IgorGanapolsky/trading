"""RAG Query Rewriter & Synonym Expansion Engine.

Expands short agentic trading queries into domain-enriched search queries
to boost vector and BM25 retrieval recall for risk rules and strategy lessons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import re
from dataclasses import field

logger = logging.getLogger(__name__)

DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "put credit": ["short put spread", "credit spread", "put spread", "15 delta", "45 dte"],
    "iron condor": ["4-leg spread", "short strangle defined risk", "50% profit target", "7 dte exit"],
    "circuit breaker": ["drawdown kill switch", "5% account protection", "trading halt"],
    "bogleheads": ["three fund portfolio", "bogleheads forum", "long term buy and hold"],
    "section 1256": ["xsp", "spx", "60/40 tax treatment", "index options"],
    "ic": ["iron condor", "neutral credit spread"],
    "1256": ["section 1256", "xsp index option", "60/40 tax treatment"],
}

TICKER_REGEX = re.compile(r"\b(SPY|XSP|SPX|QQQ|IWM|SOFI|AAPL|MSFT|NVDA|TSLA)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExpandedQuery:
    original_query: str
    expanded_query: str
    synonyms_added: tuple[str, ...] = field(default_factory=tuple)
    extracted_tickers: tuple[str, ...] = field(default_factory=tuple)


class RAGQueryRewriter:
    """Rewrites and expands queries with domain-specific trading terms."""

    def rewrite(self, query: str) -> ExpandedQuery:
        q_lower = query.lower().strip()
        added: list[str] = []

        extracted_tickers = tuple(dict.fromkeys(t.upper() for t in TICKER_REGEX.findall(query)))

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
            extracted_tickers=extracted_tickers,
        )


# Backward-compatible alias
QueryRewriter = RAGQueryRewriter
