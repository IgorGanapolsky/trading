"""Official Graphify-Labs/graphify graph.json contract.

Mirrors graphify.validate: nodes need id/label/file_type/source_file; edges
need source/target/relation/confidence/source_file. Confidence is
EXTRACTED | INFERRED | AMBIGUOUS. Accepts NetworkX ``links`` as an edges alias.
"""

from __future__ import annotations

from typing import Any

CONFIDENCE_EXTRACTED = "EXTRACTED"
CONFIDENCE_INFERRED = "INFERRED"
CONFIDENCE_AMBIGUOUS = "AMBIGUOUS"
VALID_CONFIDENCES = frozenset({CONFIDENCE_EXTRACTED, CONFIDENCE_INFERRED, CONFIDENCE_AMBIGUOUS})
VALID_FILE_TYPES = frozenset({"code", "document", "paper", "image", "rationale", "concept"})
REQUIRED_NODE_FIELDS = frozenset({"id", "label", "file_type", "source_file"})
REQUIRED_EDGE_FIELDS = frozenset({"source", "target", "relation", "confidence", "source_file"})

OFFICIAL_PYPI_PACKAGE = "graphifyy"
OFFICIAL_CLI_NAME = "graphify"
OFFICIAL_REPO = "https://github.com/Graphify-Labs/graphify"
WRONG_PIP_PACKAGES = ("graphify",)
FORBIDDEN_INSTALL_SNIPPETS = (
    "pip show graphify",
    "pip install graphify",
    "pip install git+https://github.com/Graphify-Labs/graphify.git",
    "python -m graphify .",
)
RETRIEVAL_HTML_NAMES = frozenset({"graph.html", "graph_tree.html", "GRAPH_TREE.html"})


def edge_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return edges from official ``edges`` or NetworkX ``links``."""
    if "edges" in payload and isinstance(payload["edges"], list):
        return payload["edges"]
    links = payload.get("links")
    return links if isinstance(links, list) else []


def validate_graphify_payload(data: object) -> list[str]:
    """Return schema errors; empty list means the payload matches Graphify."""
    if not isinstance(data, dict):
        return ["Extraction must be a JSON object"]

    errors: list[str] = []
    node_ids: set[str] = set()

    nodes = data.get("nodes")
    if "nodes" not in data:
        errors.append("Missing required key 'nodes'")
    elif not isinstance(nodes, list):
        errors.append("'nodes' must be a list")
    else:
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"Node {i} must be an object")
                continue
            for field in REQUIRED_NODE_FIELDS:
                if field not in node:
                    errors.append(
                        f"Node {i} (id={node.get('id', '?')!r}) missing required field '{field}'"
                    )
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id:
                node_ids.add(node_id)
            file_type = node.get("file_type")
            if file_type is not None and file_type not in VALID_FILE_TYPES:
                errors.append(
                    f"Node {i} (id={node.get('id', '?')!r}) has invalid file_type '{file_type}'"
                )

    if "edges" not in data and "links" not in data:
        errors.append("Missing required key 'edges'")
        return errors

    edges = edge_list(data)
    if "edges" in data and not isinstance(data.get("edges"), list) and "links" not in data:
        errors.append("'edges' must be a list")
        return errors

    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"Edge {i} must be an object")
            continue
        for field in REQUIRED_EDGE_FIELDS:
            if field not in edge:
                errors.append(f"Edge {i} missing required field '{field}'")
        confidence = edge.get("confidence")
        if confidence is not None and confidence not in VALID_CONFIDENCES:
            errors.append(
                f"Edge {i} has invalid confidence '{confidence}' "
                f"- must be one of {sorted(VALID_CONFIDENCES)}"
            )
        for endpoint in ("source", "target"):
            val = edge.get(endpoint)
            if isinstance(val, str) and node_ids and val not in node_ids:
                errors.append(f"Edge {i} {endpoint} '{val}' does not match any node id")

    return errors


def is_html_visualization(path: str) -> bool:
    """True when a path is Graphify HTML (visualization, never retrieval)."""
    normalized = path.replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    if name in {item.lower() for item in RETRIEVAL_HTML_NAMES}:
        return True
    return "graphify-out/" in normalized and name.endswith(".html")
