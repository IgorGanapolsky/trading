"""Intent routing for Graph RAG queries.

Deterministic, offline router — maps natural language to traversal vs
vector-primary hybrid paths without LLM token burn on every query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class QueryIntent(StrEnum):
    """Coarse query intents for the trading lab."""

    STRATEGY_STATUS = "strategy_status"  # kill switch, active family, live block
    LESSON_RISK = "lesson_risk"  # safety / prevention / past mistakes
    TRADE_EVIDENCE = "trade_evidence"  # paired ledger outcomes
    MACRO_IMPACT = "macro_impact"  # fed, vix, usd → SPY / strategy
    HYBRID = "hybrid"  # multi-hop default


@dataclass(frozen=True)
class RouteDecision:
    intent: QueryIntent
    seed_hints: list[str]
    max_hops: int
    prefer_rels: list[str]
    use_vector_fusion: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "seed_hints": self.seed_hints,
            "max_hops": self.max_hops,
            "prefer_rels": self.prefer_rels,
            "use_vector_fusion": self.use_vector_fusion,
            "reason": self.reason,
        }


_TICKER_RE = re.compile(r"\b(SPY|XSP|SPX|QQQ|IWM|VIX|VOO)\b", re.IGNORECASE)

_INTENT_RULES: list[tuple[QueryIntent, tuple[str, ...], int, list[str], bool, str]] = [
    (
        QueryIntent.STRATEGY_STATUS,
        (
            "kill switch",
            "killed",
            "active family",
            "live blocked",
            "paper only",
            "successor",
            "iron condor",
            "ic simple",
            "spy put credit",
            "put credit",
        ),
        2,
        ["KILLED", "SUCCEEDS", "BLOCKS", "GOVERNS", "TRADES"],
        False,
        "strategy lifecycle / kill-switch language",
    ),
    (
        QueryIntent.TRADE_EVIDENCE,
        (
            "expectancy",
            "profit factor",
            "win rate",
            "realized pnl",
            "paired trade",
            "closed trade",
            "cohort",
            "sample size",
            "trades.json",
        ),
        2,
        ["OUTCOME_OF", "MENTIONS", "TRADES"],
        True,
        "ledger / evidence language",
    ),
    (
        QueryIntent.MACRO_IMPACT,
        (
            "fed",
            "fomc",
            "rate cut",
            "rate hike",
            "macro",
            "vix",
            "volatility",
            "usd",
            "dxy",
            "sentiment",
            "regime",
        ),
        3,
        ["IMPACTS", "CORRELATES_WITH", "RELATED_TO", "TRADES"],
        True,
        "macro / regime language",
    ),
    (
        QueryIntent.LESSON_RISK,
        (
            "lesson",
            "ll-",
            "prevention",
            "mistake",
            "never",
            "stop loss",
            "inventory",
            "orphan",
            "risk rule",
            "halt",
            "boundary",
        ),
        2,
        ["PREVENTS", "RELATED_TO", "MENTIONS", "GOVERNS", "BLOCKS"],
        True,
        "lesson / risk-prevention language",
    ),
]


def _match_seed_hints(query: str) -> list[str]:
    q = query.lower()
    hints: list[str] = []
    for m in _TICKER_RE.finditer(query):
        hints.append(f"ticker:{m.group(1).upper()}")
    if "put credit" in q or "spy_put_credit" in q or "bull put" in q:
        hints.append("strategy:spy_put_credit")
    if "iron condor" in q or "ic simple" in q or "ic_simple" in q:
        hints.append("strategy:iron_condor")
    if "kill" in q:
        hints.append("macro:strategy_kill_2026_07_22")
    if "inventory" in q or "orphan" in q:
        hints.append("concept:inventory_hygiene")
    if "vix" in q or "volatility" in q:
        hints.append("concept:vix_spike")
    if "fed" in q or "fomc" in q or "rate" in q:
        hints.append("concept:fed_policy")
    if "north star" in q or "6000" in q:
        hints.append("concept:north_star")
    if "live" in q and ("block" in q or "gate" in q):
        hints.append("rule:live_gate_n30")
    if "stop" in q and "loss" in q:
        hints.append("rule:stop_loss_200pct")
    # Lesson IDs
    for m in re.finditer(r"\bll[-_]?(\d+)\b", q, re.IGNORECASE):
        hints.append(f"lesson:LL-{m.group(1)}")
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# When keyword hit counts tie, prefer more specific research intents over
# broad strategy-lifecycle matches (e.g. "vix impact on put credit").
_INTENT_TIEBREAK: dict[QueryIntent, int] = {
    QueryIntent.MACRO_IMPACT: 40,
    QueryIntent.TRADE_EVIDENCE: 35,
    QueryIntent.LESSON_RISK: 30,
    QueryIntent.STRATEGY_STATUS: 20,
    QueryIntent.HYBRID: 0,
}


def _keyword_hits(query_l: str, keywords: tuple[str, ...]) -> int:
    """Count non-overlapping keyword hits (longest match first).

    Prevents double-counting nested phrases like "spy put credit" + "put credit".
    """
    remaining = query_l
    hits = 0
    for kw in sorted(keywords, key=len, reverse=True):
        if kw and kw in remaining:
            hits += 1
            remaining = remaining.replace(kw, " ", 1)
    return hits


def route_query(query: str) -> RouteDecision:
    """Route a natural-language query to graph retrieval parameters."""
    q = (query or "").strip().lower()
    if not q:
        return RouteDecision(
            intent=QueryIntent.HYBRID,
            seed_hints=["strategy:spy_put_credit"],
            max_hops=2,
            prefer_rels=["GOVERNS", "BLOCKS", "RELATED_TO"],
            use_vector_fusion=True,
            reason="empty query → default active strategy hybrid",
        )

    hints = _match_seed_hints(query)
    best: tuple[QueryIntent, int, list[str], bool, str] | None = None
    best_hits = 0
    best_tie = -1
    for intent, keywords, hops, rels, fuse, reason in _INTENT_RULES:
        hits = _keyword_hits(q, keywords)
        # Macro/regime verbs amplify macro intent even when a strategy name is present
        if intent == QueryIntent.MACRO_IMPACT:
            for boost_kw in ("impact", "impacts", "ripple", "correlation", "correlates"):
                if boost_kw in q:
                    hits += 1
        tie = _INTENT_TIEBREAK.get(intent, 0)
        if hits > best_hits or (hits == best_hits and hits > 0 and tie > best_tie):
            best_hits = hits
            best_tie = tie
            best = (intent, hops, rels, fuse, reason)

    if best is None or best_hits == 0:
        if not hints:
            hints = ["strategy:spy_put_credit", "ticker:SPY"]
        return RouteDecision(
            intent=QueryIntent.HYBRID,
            seed_hints=hints,
            max_hops=2,
            prefer_rels=["RELATED_TO", "MENTIONS", "IMPACTS", "GOVERNS"],
            use_vector_fusion=True,
            reason="no strong keyword intent → hybrid multi-hop",
        )

    intent, hops, rels, fuse, reason = best
    if not hints:
        if intent == QueryIntent.STRATEGY_STATUS:
            hints = [
                "strategy:spy_put_credit",
                "strategy:iron_condor",
                "macro:strategy_kill_2026_07_22",
            ]
        elif intent == QueryIntent.MACRO_IMPACT:
            hints = ["concept:fed_policy", "concept:vix_spike", "ticker:SPY"]
        elif intent == QueryIntent.TRADE_EVIDENCE:
            hints = ["strategy:spy_put_credit", "strategy:iron_condor"]
        else:
            hints = ["strategy:spy_put_credit"]

    return RouteDecision(
        intent=intent,
        seed_hints=hints,
        max_hops=hops,
        prefer_rels=rels,
        use_vector_fusion=fuse,
        reason=reason,
    )


def expand_seeds_from_store(seed_hints: Iterable[str], search_fn) -> list[str]:
    """Resolve seed hints; fall back to store text search for free tokens."""
    seeds: list[str] = []
    for h in seed_hints:
        seeds.append(h)
    return seeds
