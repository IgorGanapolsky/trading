"""Financial knowledge-graph ontology for the trading lab.

Nodes bridge strategies, lessons, broker-paired trades, and macro/regime
anchors. Edges carry temporal validity (Graphiti-style) so kill decisions and
correlations can expire without deleting history.
"""

from __future__ import annotations

from enum import StrEnum


class NodeType(StrEnum):
    """Entity types in the financial graph."""

    TICKER = "ticker"
    STRATEGY = "strategy"
    LESSON = "lesson"
    TRADE = "trade"
    RULE = "rule"
    MACRO_EVENT = "macro_event"
    REGIME = "regime"
    SIGNAL = "signal"
    SECTOR = "sector"
    CONCEPT = "concept"


class EdgeRel(StrEnum):
    """Directional temporal relationships."""

    MENTIONS = "MENTIONS"
    IMPACTS = "IMPACTS"
    CORRELATES_WITH = "CORRELATES_WITH"
    CAUSED_BY = "CAUSED_BY"
    PREVENTS = "PREVENTS"
    KILLED = "KILLED"
    SUCCEEDS = "SUCCEEDS"
    ANCHORS = "ANCHORS"
    BLOCKS = "BLOCKS"
    CONTAINS = "CONTAINS"
    RELATED_TO = "RELATED_TO"
    OUTCOME_OF = "OUTCOME_OF"
    GOVERNS = "GOVERNS"
    TRADES = "TRADES"


# Canonical seed entities for the SPY put-credit lab (not generic multi-name alpha).
SEED_TICKERS: tuple[str, ...] = ("SPY", "XSP", "SPX", "QQQ", "VIX", "IWM")

SEED_STRATEGIES: dict[str, dict] = {
    "spy_put_credit": {
        "label": "SPY bull put credit (active validation)",
        "status": "active",
        "paper_only": True,
    },
    "iron_condor": {
        "label": "Iron condor / IC Simple (killed)",
        "status": "killed",
        "paper_only": True,
    },
    "ic_simple": {
        "label": "IC Simple alias (killed)",
        "status": "killed",
        "paper_only": True,
    },
    "residual_ic": {
        "label": "Residual IC exit-only inventory",
        "status": "exit_only",
        "paper_only": True,
    },
}

# Hard risk rules that must surface for strategy queries.
SEED_RULES: dict[str, str] = {
    "rule:stop_loss_200pct": "Close at 200% of credit loss (stop)",
    "rule:profit_target_25pct": "Close at 25% of max profit",
    "rule:time_exit_7dte": "Forced exit at 7 DTE",
    "rule:max_1_lot": "Max 1-lot per structure",
    "rule:max_2_concurrent_put_credits": "Max 2 concurrent put-credit structures",
    "rule:max_3_structures_per_day": "Max 3 new put-credit structures per day",
    "rule:paper_only": "Paper-only; live blocked until cohort gates clear",
    "rule:live_gate_n30": "Live blocked until n>=30, expectancy>0, PF>1",
    "rule:no_new_ic_entries": "New iron-condor entries forbidden",
}

# Simple macro/regime concepts useful for dual-level retrieval.
SEED_CONCEPTS: dict[str, str] = {
    "concept:vix_spike": "Elevated VIX / vol shock regime",
    "concept:fed_policy": "Fed rate / FOMC policy path",
    "concept:usd_strength": "USD macro strength / DXY path",
    "concept:inventory_hygiene": "Open inventory lot/journal reconciliation",
    "concept:north_star": "North Star $6k/mo after-tax passive income",
}

TICKER_PATTERN_SOURCES: tuple[str, ...] = (
    "SPY",
    "XSP",
    "SPX",
    "QQQ",
    "IWM",
    "VIX",
    "VOO",
    "NVDA",
    "AAPL",
    "TSLA",
    "AMZN",
    "META",
    "GOOG",
    "AMD",
    "MSFT",
)
