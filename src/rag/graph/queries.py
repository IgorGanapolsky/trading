"""Multi-hop questions over the trade graph.

Each function here answers something that vector retrieval structurally cannot, because
the answer is a join across entities rather than a passage in a document:

* `policy_cohorts`     -- did changing this risk parameter change the outcome?
* `loss_attribution`   -- which exit path is actually bleeding, per strategy?
* `explain_trade`      -- the causal chain around one structure.
* `graph_context`      -- a bounded subgraph serialized for a language model.

Every aggregate reports its own sample size and refuses to emit ratios that the sample
cannot support. Cohort statistics on n=3 are noise wearing a decimal point.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.rag.graph.temporal_graph import Subgraph, TemporalGraph

# Below this, ratio metrics are withheld rather than reported. Mirrors the n>=30
# promotion gate in .claude/rules/kill-criteria.md.
MIN_COHORT_FOR_RATIOS = 30

# Only broker-reconciled paired closes may enter a metric. Entry-journal rows can be
# open, carry no realized P/L, and per data-integrity.md "unmatched orders are never
# trades". Counting them inflates sample size toward the n>=30 live-capital gate --
# the one direction an error here must never go.
SCORING_TIER = "paired_ledger"


def _is_scorable(trade_attrs: dict[str, Any]) -> bool:
    return trade_attrs.get("evidence_tier", SCORING_TIER) == SCORING_TIER


@dataclass
class Cohort:
    """Trades sharing one policy value, with row-derived metrics."""

    key: str
    label: str
    valid_from: str | None
    valid_to: str | None
    trade_ids: list[str] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    @property
    def n(self) -> int:
        return len(self.trade_ids)

    @property
    def realized_pnl(self) -> float:
        return round(self.gross_profit - self.gross_loss, 2)

    def metrics(self) -> dict[str, Any]:
        """Row-derived metrics. Ratios are None until the sample supports them."""
        base: dict[str, Any] = {
            "n": self.n,
            "wins": self.wins,
            "losses": self.losses,
            "breakeven": self.breakeven,
            "realized_pnl": self.realized_pnl,
            "sufficient_sample": self.n >= MIN_COHORT_FOR_RATIOS,
        }
        if self.n == 0:
            base.update(win_rate=None, expectancy=None, profit_factor=None)
            return base

        base["expectancy"] = round(self.realized_pnl / self.n, 2)
        if self.n < MIN_COHORT_FOR_RATIOS:
            # Withheld on purpose: a 3-trade "profit factor" invites exactly the
            # over-reading that killed the previous strategy.
            base.update(win_rate=None, profit_factor=None)
            base["note"] = f"n={self.n} < {MIN_COHORT_FOR_RATIOS}; ratios withheld"
            return base

        base["win_rate"] = round(self.wins / self.n, 4)
        base["profit_factor"] = (
            round(self.gross_profit / self.gross_loss, 4) if self.gross_loss > 0 else None
        )
        return base


def _accumulate(cohort: Cohort, trade_attrs: dict[str, Any], trade_id: str) -> None:
    pnl = float(trade_attrs.get("realized_pnl") or 0.0)
    outcome = trade_attrs.get("outcome")
    cohort.trade_ids.append(trade_id)
    if outcome == "win":
        cohort.wins += 1
    elif outcome == "loss":
        cohort.losses += 1
    else:
        cohort.breakeven += 1
    if pnl >= 0:
        cohort.gross_profit += pnl
    else:
        cohort.gross_loss += abs(pnl)


def policy_cohorts(
    graph: TemporalGraph,
    policy_name: str,
    strategy: str | None = None,
) -> list[dict[str, Any]]:
    """Split trades by the policy value in force at entry, and score each cohort.

    This is the question a stop-loss change actually poses -- "was the cohort under the
    new value better than the cohort under the old one" -- and it needs the temporal
    edge to answer, because today's constants file says nothing about March.
    """
    cohorts: dict[str, Cohort] = {}

    for policy_node in graph.nodes_of_kind("policy"):
        if policy_node.attrs.get("name") != policy_name:
            continue
        cohort = Cohort(
            key=policy_node.id,
            label=policy_node.label,
            valid_from=policy_node.valid_from,
            valid_to=policy_node.valid_to,
        )
        for _edge, neighbor_id in graph.neighbors(
            policy_node.id, rels=["GOVERNED_BY"], direction="in"
        ):
            trade = graph.get_node(neighbor_id)
            if trade is None or trade.kind != "trade":
                continue
            if not _is_scorable(trade.attrs):
                continue
            if strategy and trade.attrs.get("strategy") != strategy:
                continue
            _accumulate(cohort, trade.attrs, trade.id)
        cohorts[policy_node.id] = cohort

    ordered = sorted(cohorts.values(), key=lambda c: c.valid_from or "")
    return [
        {
            "policy": policy_name,
            "value": graph.get_node(c.key).attrs.get("value") if graph.get_node(c.key) else None,
            "valid_from": c.valid_from,
            "valid_to": c.valid_to,
            **c.metrics(),
        }
        for c in ordered
        if c.n > 0
    ]


def loss_attribution(graph: TemporalGraph, strategy: str | None = None) -> dict[str, Any]:
    """Decompose realized losses by exit path and strategy.

    Reports `unrecorded` exits explicitly instead of dropping them, because an
    attribution table that quietly omits most of the ledger reads as complete when it
    is not.
    """
    by_reason: dict[str, Cohort] = {}
    by_strategy: dict[str, Cohort] = {}
    excluded: dict[str, int] = defaultdict(int)

    for trade in graph.nodes_of_kind("trade"):
        if strategy and trade.attrs.get("strategy") != strategy:
            continue
        if not _is_scorable(trade.attrs):
            # Counted nowhere, reported here. Silently dropping these would hide that
            # the ledger and the journal disagree about how many trades exist.
            excluded[trade.attrs.get("evidence_tier", "unknown")] += 1
            continue
        reason = trade.attrs.get("exit_reason") or "unrecorded"
        strat = trade.attrs.get("strategy") or "unknown"

        cohort = by_reason.setdefault(
            reason, Cohort(key=reason, label=reason, valid_from=None, valid_to=None)
        )
        _accumulate(cohort, trade.attrs, trade.id)

        scohort = by_strategy.setdefault(
            strat, Cohort(key=strat, label=strat, valid_from=None, valid_to=None)
        )
        _accumulate(scohort, trade.attrs, trade.id)

    total = sum(c.n for c in by_reason.values())
    recorded = sum(c.n for c in by_reason.values() if c.key != "unrecorded")

    return {
        "total_trades": total,
        "scoring_tier": SCORING_TIER,
        "excluded_non_scorable": dict(excluded),
        "exit_reason_recorded": recorded,
        "exit_reason_coverage": round(recorded / total, 4) if total else None,
        "by_exit_reason": sorted(
            ({"exit_reason": k, **c.metrics()} for k, c in by_reason.items()),
            key=lambda r: r["realized_pnl"],
        ),
        "by_strategy": sorted(
            ({"strategy": k, **c.metrics()} for k, c in by_strategy.items()),
            key=lambda r: r["realized_pnl"],
        ),
    }


def explain_trade(graph: TemporalGraph, trade_id: str, hops: int = 2) -> dict[str, Any]:
    """The causal neighbourhood of one structure: policy, outcome, exit, lessons."""
    node_id = trade_id if trade_id.startswith("trade:") else f"trade:{trade_id}"
    trade = graph.get_node(node_id)
    if trade is None:
        return {"error": f"unknown trade: {trade_id}"}

    sub = graph.expand([node_id], hops=hops, node_budget=80)
    governed_by = [
        graph.get_node(e.dst) for e in sub.edges if e.src == node_id and e.rel == "GOVERNED_BY"
    ]
    return {
        "trade": {"id": trade.id, "label": trade.label, **trade.attrs},
        "entry": trade.valid_from,
        "exit": trade.valid_to,
        "governed_by": [
            {"policy": n.attrs.get("name"), "value": n.attrs.get("value"), "since": n.valid_from}
            for n in governed_by
            if n is not None
        ],
        "related_lessons": [n.label for n in sub.by_kind("lesson")],
        "subgraph_size": len(sub),
        "truncated": sub.truncated,
    }


def graph_context(
    graph: TemporalGraph,
    seeds: list[str],
    hops: int = 2,
    node_budget: int = 60,
    as_of: str | None = None,
) -> str:
    """Serialize a bounded subgraph into compact text for a language model.

    The node budget is enforced during traversal rather than by truncating the string
    afterwards, so the cost ceiling holds regardless of how dense the seed region is.
    Truncation is stated in the output -- a partial subgraph must never read as the
    whole picture.
    """
    sub = graph.expand(seeds, hops=hops, node_budget=node_budget, as_of=as_of)
    if not sub.nodes:
        return "No graph context found for the given seeds."

    lines: list[str] = []
    if as_of:
        lines.append(f"# Graph context as of {as_of}")
    lines.append(f"# {len(sub.nodes)} entities, {len(sub.edges)} relationships")
    if sub.truncated:
        lines.append(f"# TRUNCATED at node budget {node_budget} -- this subgraph is incomplete")

    grouped: dict[str, list[str]] = defaultdict(list)
    for node in sub.nodes.values():
        window = ""
        if node.valid_from:
            window = f" [{node.valid_from[:10]}..{(node.valid_to or 'open')[:10]}]"
        grouped[node.kind].append(f"  - {node.label}{window}")

    lines.append("\n## Entities")
    for kind in sorted(grouped):
        lines.append(f"\n### {kind} ({len(grouped[kind])})")
        lines.extend(sorted(grouped[kind])[:25])
        if len(grouped[kind]) > 25:
            lines.append(f"  ... {len(grouped[kind]) - 25} more {kind} entities omitted")

    lines.append("\n## Relationships")
    for edge in sub.edges[:60]:
        src = sub.nodes.get(edge.src)
        dst = sub.nodes.get(edge.dst)
        if src is None or dst is None:
            continue
        lines.append(f"  ({src.label}) -[{edge.rel}]-> ({dst.label})")
    if len(sub.edges) > 60:
        lines.append(f"  ... {len(sub.edges) - 60} more relationships omitted")

    return "\n".join(lines)


def seeds_from_terms(graph: TemporalGraph, terms: list[str], limit: int = 10) -> list[str]:
    """Resolve free-text terms to node ids by label match.

    Deliberately dumb: the existing hybrid retriever already does semantic ranking. The
    graph's job is expansion from an anchor, not competing at relevance scoring.
    """
    wanted = [t.lower() for t in terms if t.strip()]
    if not wanted:
        return []
    hits: list[tuple[int, str]] = []
    for kind in ("strategy", "policy", "policy_name", "exit_reason", "lesson", "outcome"):
        for node in graph.nodes_of_kind(kind):
            haystack = f"{node.id} {node.label}".lower()
            score = sum(1 for term in wanted if term in haystack)
            if score:
                hits.append((score, node.id))
    hits.sort(key=lambda pair: (-pair[0], pair[1]))
    return [node_id for _, node_id in hits[:limit]]


def subgraph_summary(sub: Subgraph) -> dict[str, Any]:
    """Compact stats for logging and tests."""
    kinds: dict[str, int] = defaultdict(int)
    for node in sub.nodes.values():
        kinds[node.kind] += 1
    return {
        "nodes": len(sub.nodes),
        "edges": len(sub.edges),
        "kinds": dict(kinds),
        "truncated": sub.truncated,
    }
