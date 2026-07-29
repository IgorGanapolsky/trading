"""Query Rewriter for Financial and Options Trading RAG.

Expands technical trading abbreviations, normalizes ticker symbols, and generates
multi-query expansions for hybrid vector + BM25 search.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Common options trading & financial domain expansions
DOMAIN_EXPANSIONS: dict[str, list[str]] = {
    "ic": ["iron condor", "neutral credit spread"],
    "csp": ["cash secured put", "bull put credit"],
    "1256": ["section 1256", "tax optimization", "xsp index option"],
    "pdt": ["pattern day trader", "equity margin restriction"],
    "vix": ["volatility index", "regime spike"],
    "stop": ["stop loss", "max loss limit", "200% credit stop"],
    "dte": ["days to expiration", "time decay"],
    "ivr": ["iv rank", "implied volatility rank"],
}


@dataclass(frozen=True)
class RewrittenQuery:
    original_query: str
    expanded_query: str
    extracted_tickers: list[str] = field(default_factory=list)
    key_terms: list[str] = field(default_factory=list)


class QueryRewriter:
    """Domain-aware query rewriter for trading RAG retrieval."""

    def __init__(self, expansions: dict[str, list[str]] | None = None):
        self.expansions = expansions or DOMAIN_EXPANSIONS
        self.ticker_pattern = re.compile(r"\b(SPY|XSP|SPX|QQQ|IWM|SOFI|AAPL|MSFT|NVDA|TSLA)\b", re.IGNORECASE)

    def rewrite(self, query: str) -> RewrittenQuery:
        if not query or not query.strip():
            return RewrittenQuery(original_query="", expanded_query="")

        raw_query = query.strip()
        tokens = raw_query.lower().split()
        expanded_parts = [raw_query]
        extracted_tickers = [t.upper() for t in self.ticker_pattern.findall(raw_query)]
        key_terms = []

        for token in tokens:
            cleaned = re.sub(r"[^\w]", "", token)
            if cleaned in self.expansions:
                expansion_terms = self.expansions[cleaned]
                expanded_parts.extend(expansion_terms)
                key_terms.extend(expansion_terms)
            elif len(cleaned) > 2:
                key_terms.append(cleaned)

        expanded_query = " ".join(dict.fromkeys(expanded_parts))
        return RewrittenQuery(
            original_query=raw_query,
            expanded_query=expanded_query,
            extracted_tickers=list(dict.fromkeys(extracted_tickers)),
            key_terms=list(dict.fromkeys(key_terms)),
        )
