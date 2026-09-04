"""Official Graphify-Labs/graphify adapter (code graph, not financial Graph RAG).

Package on PyPI is ``graphifyy``. CLI command is ``graphify``. Retrieval is
``graph.json`` via query/path/explain. ``graph.html`` is visualization only.
"""

from src.rag.graphify.contract import (
    CONFIDENCE_AMBIGUOUS,
    CONFIDENCE_EXTRACTED,
    CONFIDENCE_INFERRED,
    VALID_CONFIDENCES,
    validate_graphify_payload,
)
from src.rag.graphify.fuse import fuse_hits_with_graph
from src.rag.graphify.graph import CodeGraph, load_code_graph

__all__ = [
    "CONFIDENCE_AMBIGUOUS",
    "CONFIDENCE_EXTRACTED",
    "CONFIDENCE_INFERRED",
    "VALID_CONFIDENCES",
    "CodeGraph",
    "fuse_hits_with_graph",
    "load_code_graph",
    "validate_graphify_payload",
]
