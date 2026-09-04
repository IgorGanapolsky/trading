"""Load and traverse official graph.json (stdlib; no NetworkX/Gremlin)."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.rag.graphify.contract import edge_list, validate_graphify_payload

_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "what",
        "which",
        "who",
        "how",
        "does",
        "do",
        "is",
        "are",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "from",
        "calls",
        "call",
        "connect",
        "connects",
        "between",
        "show",
        "me",
        "trace",
    }
)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    file_type: str
    source_file: str
    source_location: str = ""
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "file_type": self.file_type,
            "source_file": self.source_file,
            "source_location": self.source_location,
        }


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    confidence: str
    source_file: str
    source_location: str = ""
    confidence_score: float | None = None
    context: str = ""
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "confidence": self.confidence,
            "source_file": self.source_file,
            "source_location": self.source_location,
        }
        if self.confidence_score is not None:
            payload["confidence_score"] = self.confidence_score
        if self.context:
            payload["context"] = self.context
        return payload


class CodeGraph:
    """Undirected adjacency over official Graphify node-link JSON."""

    def __init__(self, payload: dict[str, Any], *, path: Path | None = None):
        errors = validate_graphify_payload(payload)
        if errors:
            raise ValueError("graph.json is not a Graphify payload:\n" + "\n".join(errors))
        self.path = path
        self.payload = payload
        self.nodes: dict[str, GraphNode] = {}
        for raw in payload.get("nodes") or []:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            node_id = str(raw["id"])
            self.nodes[node_id] = GraphNode(
                id=node_id,
                label=str(raw.get("label") or node_id),
                file_type=str(raw.get("file_type") or ""),
                source_file=str(raw.get("source_file") or ""),
                source_location=str(raw.get("source_location") or ""),
                raw=raw,
            )
        self.edges: list[GraphEdge] = []
        self._adj: dict[str, list[tuple[str, GraphEdge]]] = defaultdict(list)
        for raw in edge_list(payload):
            if not isinstance(raw, dict):
                continue
            source = str(raw.get("source") or "")
            target = str(raw.get("target") or "")
            if not source or not target:
                continue
            score = raw.get("confidence_score")
            edge = GraphEdge(
                source=source,
                target=target,
                relation=str(raw.get("relation") or ""),
                confidence=str(raw.get("confidence") or ""),
                source_file=str(raw.get("source_file") or ""),
                source_location=str(raw.get("source_location") or ""),
                confidence_score=float(score) if isinstance(score, (int, float)) else None,
                context=str(raw.get("context") or ""),
                raw=raw,
            )
            self.edges.append(edge)
            self._adj[source].append((target, edge))
            self._adj[target].append((source, edge))

    def confidence_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for edge in self.edges:
            counts[edge.confidence] = counts.get(edge.confidence, 0) + 1
        return counts

    def match_nodes(self, needle: str) -> list[GraphNode]:
        text = needle.strip()
        if not text:
            return []
        exact: list[GraphNode] = []
        fuzzy: list[GraphNode] = []
        lowered = text.lower()
        compact = _norm(text)
        for node in self.nodes.values():
            hay = f"{node.id} {node.label} {node.source_file}".lower()
            if node.id == text or node.label == text:
                exact.append(node)
            elif lowered in hay or (compact and compact in _norm(hay)):
                fuzzy.append(node)
        return exact or fuzzy

    def neighbors(self, node_id: str, *, max_hops: int = 1) -> list[GraphEdge]:
        if node_id not in self.nodes or max_hops < 1:
            return []
        seen_edges: set[tuple[str, str, str, str]] = set()
        found: list[GraphEdge] = []
        frontier = {node_id}
        visited = {node_id}
        for _ in range(max_hops):
            nxt: set[str] = set()
            for current in frontier:
                for neighbor, edge in self._adj.get(current, ()):
                    key = (edge.source, edge.target, edge.relation, edge.confidence)
                    if key not in seen_edges:
                        seen_edges.add(key)
                        found.append(edge)
                    if neighbor not in visited:
                        visited.add(neighbor)
                        nxt.add(neighbor)
            frontier = nxt
            if not frontier:
                break
        return found

    def shortest_path(self, start: str, goal: str) -> list[dict[str, Any]] | None:
        start_nodes = self.match_nodes(start)
        goal_nodes = self.match_nodes(goal)
        if not start_nodes or not goal_nodes:
            return None
        goal_ids = {node.id for node in goal_nodes}
        origin = start_nodes[0].id
        if origin in goal_ids:
            node = self.nodes[origin]
            return [{"node": node.to_dict(), "via": None}]
        prev: dict[str, tuple[str, GraphEdge]] = {}
        queue: deque[str] = deque([origin])
        seen = {origin}
        found_id: str | None = None
        while queue:
            current = queue.popleft()
            for neighbor, edge in self._adj.get(current, ()):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                prev[neighbor] = (current, edge)
                if neighbor in goal_ids:
                    found_id = neighbor
                    queue.clear()
                    break
                queue.append(neighbor)
        if found_id is None:
            return None
        hops: list[tuple[str, GraphEdge | None]] = []
        cursor = found_id
        while cursor != origin:
            parent, edge = prev[cursor]
            hops.append((cursor, edge))
            cursor = parent
        hops.append((origin, None))
        hops.reverse()
        trail: list[dict[str, Any]] = []
        for node_id, edge in hops:
            trail.append(
                {
                    "node": self.nodes[node_id].to_dict(),
                    "via": edge.to_dict() if edge is not None else None,
                }
            )
        return trail

    def explain(self, needle: str) -> dict[str, Any] | None:
        matches = self.match_nodes(needle)
        if not matches:
            return None
        node = matches[0]
        connections = []
        for neighbor, edge in self._adj.get(node.id, ()):
            other = self.nodes[neighbor]
            inbound = edge.target == node.id
            connections.append(
                {
                    "direction": "in" if inbound else "out",
                    "neighbor": other.to_dict(),
                    "edge": edge.to_dict(),
                }
            )
        return {
            "node": node.to_dict(),
            "degree": len(connections),
            "connections": connections,
            "validity_window": None,
            "note": "Graphify AST edges have no validity window",
        }

    def query(self, question: str, *, max_hops: int = 2, budget_nodes: int = 24) -> dict[str, Any]:
        tokens = [tok for tok in _TOKEN_RE.findall(question.lower()) if tok not in _STOP]
        seeds: list[GraphNode] = []
        seen: set[str] = set()
        for token in tokens or _TOKEN_RE.findall(question.lower()):
            for node in self.match_nodes(token):
                if node.id not in seen:
                    seen.add(node.id)
                    seeds.append(node)
        if not seeds:
            for node in self.nodes.values():
                if question.lower() in f"{node.label} {node.source_file}".lower():
                    seeds.append(node)
                    break
        node_ids: list[str] = []
        edge_hits: list[GraphEdge] = []
        for seed in seeds:
            if seed.id not in node_ids:
                node_ids.append(seed.id)
            for edge in self.neighbors(seed.id, max_hops=max_hops):
                edge_hits.append(edge)
                for endpoint in (edge.source, edge.target):
                    if endpoint not in node_ids:
                        node_ids.append(endpoint)
        node_ids = node_ids[:budget_nodes]
        keep = set(node_ids)
        unique_edges: list[GraphEdge] = []
        seen_edge: set[tuple[str, str, str, str]] = set()
        for edge in edge_hits:
            if edge.source not in keep or edge.target not in keep:
                continue
            key = (edge.source, edge.target, edge.relation, edge.confidence)
            if key in seen_edge:
                continue
            seen_edge.add(key)
            unique_edges.append(edge)
        return {
            "question": question,
            "seeds": [self.nodes[i].to_dict() for i in node_ids if i in {s.id for s in seeds}],
            "nodes": [self.nodes[i].to_dict() for i in node_ids if i in self.nodes],
            "edges": [edge.to_dict() for edge in unique_edges],
            "max_hops": max_hops,
            "validity_window": None,
        }


def load_code_graph(path: str | Path) -> CodeGraph:
    graph_path = Path(path)
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{graph_path} is not a JSON object")
    return CodeGraph(payload, path=graph_path)


def default_graph_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / "graphify-out" / "graph.json"
