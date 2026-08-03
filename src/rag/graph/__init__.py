"""Financial Graph RAG — temporal property graph + hybrid retrieval.

Stdlib-first stack (SQLite property graph) designed for paper SPY put-credit
validation. Captures strategy/lesson/trade/regime dependencies that flat
vector RAG cannot. Optional LanceDB fusion is additive, not required.

Architecture mirrors industry Graph RAG patterns (temporal edges, hybrid
leaf nodes, intent routing, token gateway) without hard Neo4j/FalkorDB deps.
"""

from src.rag.graph.pipeline import GraphRAGPipeline, GraphRAGResult, get_graph_rag_pipeline
from src.rag.graph.router import QueryIntent, route_query
from src.rag.graph.schema import EdgeRel, NodeType
from src.rag.graph.store import FinancialGraphStore
from src.rag.graph.token_gateway import TokenGuardResult, apply_token_guard

__all__ = [
    "EdgeRel",
    "FinancialGraphStore",
    "GraphRAGPipeline",
    "GraphRAGResult",
    "NodeType",
    "QueryIntent",
    "TokenGuardResult",
    "apply_token_guard",
    "get_graph_rag_pipeline",
    "route_query",
]
