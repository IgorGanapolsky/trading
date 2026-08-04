"""Temporal knowledge graph layer over the trading system's own causal history.

Complements the existing vector/BM25 retrieval in `src.rag` rather than replacing it:
the hybrid retriever finds relevant text, this finds the joins between entities.
"""

from src.rag.graph.build import build_graph, extract_policy_history
from src.rag.graph.queries import (
    explain_trade,
    graph_context,
    loss_attribution,
    policy_cohorts,
    seeds_from_terms,
)
from src.rag.graph.temporal_graph import Edge, Node, Subgraph, TemporalGraph

__all__ = [
    "Edge",
    "Node",
    "Subgraph",
    "TemporalGraph",
    "build_graph",
    "explain_trade",
    "extract_policy_history",
    "graph_context",
    "loss_attribution",
    "policy_cohorts",
    "seeds_from_terms",
]
