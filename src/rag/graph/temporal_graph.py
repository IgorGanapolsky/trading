"""Bitemporal knowledge graph over the trading system's own causal history.

Vector RAG retrieves chunks that *look like* the query. It cannot answer a question
whose answer is a join -- "which policy was in force when this cohort lost money, and
which lesson already warned about it". No single chunk contains that; it lives in the
edges. This module stores those edges.

Temporal semantics follow the bitemporal model: every node and edge carries a validity
interval (`valid_from`, `valid_to`) describing when the fact was true in the world, plus
`ingested_at` describing when we learned it. Traversal is always `as_of` a timestamp, so
a query about March 2026 sees the risk policy that was actually in force in March 2026 --
not today's constants.

Backed by the SQLite already in the repo. No graph server, no new infrastructure.
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "rag" / "trade_graph.sqlite"

Direction = Literal["out", "in", "both"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    attrs_json  TEXT NOT NULL DEFAULT '{}',
    valid_from  TEXT,
    valid_to    TEXT,
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    src         TEXT NOT NULL,
    rel         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0,
    attrs_json  TEXT NOT NULL DEFAULT '{}',
    valid_from  TEXT,
    valid_to    TEXT,
    ingested_at TEXT NOT NULL,
    UNIQUE(src, rel, dst, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src, rel);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst, rel);
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Node:
    """A typed entity. `id` is namespaced by kind, e.g. `trade:IC_SPY_...`."""

    id: str
    kind: str
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None


@dataclass(frozen=True)
class Edge:
    """A directed, time-scoped relationship."""

    src: str
    rel: str
    dst: str
    weight: float = 1.0
    attrs: dict[str, Any] = field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None


@dataclass
class Subgraph:
    """Result of a bounded traversal.

    `truncated` is True when the node budget stopped the expansion early. Callers must
    surface that rather than presenting a partial subgraph as complete -- a truncated
    traversal that reads as exhaustive is how a graph answer becomes a confident lie.
    """

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    depth_of: dict[str, int] = field(default_factory=dict)
    truncated: bool = False

    def __len__(self) -> int:
        return len(self.nodes)

    def by_kind(self, kind: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind == kind]


def _row_to_node(row: sqlite3.Row) -> Node:
    return Node(
        id=row["id"],
        kind=row["kind"],
        label=row["label"],
        attrs=json.loads(row["attrs_json"]),
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
    )


def _row_to_edge(row: sqlite3.Row) -> Edge:
    return Edge(
        src=row["src"],
        rel=row["rel"],
        dst=row["dst"],
        weight=row["weight"],
        attrs=json.loads(row["attrs_json"]),
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
    )


class TemporalGraph:
    """SQLite-backed bitemporal property graph.

    Read paths are pure SQL over two indexed tables; a k-hop expansion on a graph of this
    size is sub-millisecond, which is several orders of magnitude inside the latency
    budget of a strategy that holds positions for 30-45 days.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> TemporalGraph:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ writes

    def add_node(self, node: Node) -> None:
        self._conn.execute(
            """INSERT INTO nodes (id, kind, label, attrs_json, valid_from, valid_to, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   kind=excluded.kind,
                   label=excluded.label,
                   attrs_json=excluded.attrs_json,
                   valid_from=excluded.valid_from,
                   valid_to=excluded.valid_to,
                   ingested_at=excluded.ingested_at""",
            (
                node.id,
                node.kind,
                node.label,
                json.dumps(node.attrs, sort_keys=True, default=str),
                node.valid_from,
                node.valid_to,
                _utcnow(),
            ),
        )

    def add_edge(self, edge: Edge) -> None:
        self._conn.execute(
            """INSERT INTO edges (src, rel, dst, weight, attrs_json, valid_from, valid_to, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(src, rel, dst, valid_from) DO UPDATE SET
                   weight=excluded.weight,
                   attrs_json=excluded.attrs_json,
                   valid_to=excluded.valid_to,
                   ingested_at=excluded.ingested_at""",
            (
                edge.src,
                edge.rel,
                edge.dst,
                edge.weight,
                json.dumps(edge.attrs, sort_keys=True, default=str),
                edge.valid_from,
                edge.valid_to,
                _utcnow(),
            ),
        )

    def add_many(self, nodes: Iterable[Node] = (), edges: Iterable[Edge] = ()) -> None:
        for node in nodes:
            self.add_node(node)
        for edge in edges:
            self.add_edge(edge)
        self._conn.commit()

    def clear(self) -> None:
        self._conn.executescript("DELETE FROM edges; DELETE FROM nodes;")
        self._conn.commit()

    # ------------------------------------------------------------------- reads

    def get_node(self, node_id: str) -> Node | None:
        row = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return _row_to_node(row) if row else None

    def nodes_of_kind(self, kind: str) -> list[Node]:
        rows = self._conn.execute("SELECT * FROM nodes WHERE kind = ? ORDER BY id", (kind,))
        return [_row_to_node(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        node_kinds = {
            r["kind"]: r["n"]
            for r in self._conn.execute("SELECT kind, COUNT(*) n FROM nodes GROUP BY kind")
        }
        edge_rels = {
            r["rel"]: r["n"]
            for r in self._conn.execute("SELECT rel, COUNT(*) n FROM edges GROUP BY rel")
        }
        return {
            "nodes": sum(node_kinds.values()),
            "edges": sum(edge_rels.values()),
            "node_kinds": node_kinds,
            "edge_relations": edge_rels,
            "db_path": str(self.db_path),
        }

    def neighbors(
        self,
        node_id: str,
        rels: Iterable[str] | None = None,
        direction: Direction = "both",
        as_of: str | None = None,
    ) -> Iterator[tuple[Edge, str]]:
        """Yield `(edge, neighbor_id)` for edges valid at `as_of`.

        An edge is valid at T when `valid_from <= T` (or is open) and `valid_to > T`
        (or is open). Passing `as_of=None` ignores time entirely.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if direction == "out":
            clauses.append("src = ?")
            params.append(node_id)
        elif direction == "in":
            clauses.append("dst = ?")
            params.append(node_id)
        else:
            clauses.append("(src = ? OR dst = ?)")
            params.extend([node_id, node_id])

        rel_list = list(rels) if rels else []
        if rel_list:
            clauses.append(f"rel IN ({','.join('?' for _ in rel_list)})")
            params.extend(rel_list)

        if as_of is not None:
            clauses.append("(valid_from IS NULL OR valid_from <= ?)")
            params.append(as_of)
            clauses.append("(valid_to IS NULL OR valid_to > ?)")
            params.append(as_of)

        # Every fragment in `clauses` is a module-literal; all user data is parameterized.
        where = " AND ".join(clauses)
        # `where` is built only from the module-literal fragments appended above; every
        # caller-supplied value goes through `params` as a bound parameter.
        sql = f"SELECT * FROM edges WHERE {where} ORDER BY weight DESC, id"  # noqa: S608 # nosec B608
        for row in self._conn.execute(sql, params):
            edge = _row_to_edge(row)
            yield edge, (edge.dst if edge.src == node_id else edge.src)

    def expand(
        self,
        seeds: Iterable[str],
        hops: int = 2,
        node_budget: int = 200,
        rels: Iterable[str] | None = None,
        direction: Direction = "both",
        as_of: str | None = None,
    ) -> Subgraph:
        """Breadth-first expansion from `seeds`, bounded by `hops` and `node_budget`.

        The budget is the cost gateway: multi-hop expansion over a dense node (an
        `outcome:loss` touching 138 trades) explodes context if left unbounded. Breadth
        is capped here, before anything reaches a model, rather than trimmed afterwards.
        """
        rel_list = list(rels) if rels else None
        sub = Subgraph()
        queue: deque[tuple[str, int]] = deque()

        for seed in seeds:
            node = self.get_node(seed)
            if node is None or seed in sub.nodes:
                continue
            sub.nodes[seed] = node
            sub.depth_of[seed] = 0
            queue.append((seed, 0))

        seen_edges: set[tuple[str, str, str, str | None]] = set()

        while queue:
            current, depth = queue.popleft()
            if depth >= hops:
                continue
            for edge, neighbor_id in self.neighbors(
                current, rels=rel_list, direction=direction, as_of=as_of
            ):
                key = (edge.src, edge.rel, edge.dst, edge.valid_from)
                if key not in seen_edges:
                    seen_edges.add(key)
                    sub.edges.append(edge)
                if neighbor_id in sub.nodes:
                    continue
                if len(sub.nodes) >= node_budget:
                    sub.truncated = True
                    return sub
                neighbor = self.get_node(neighbor_id)
                if neighbor is None:
                    continue
                sub.nodes[neighbor_id] = neighbor
                sub.depth_of[neighbor_id] = depth + 1
                queue.append((neighbor_id, depth + 1))

        return sub

    def paths(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
        as_of: str | None = None,
    ) -> list[list[Edge]]:
        """All simple paths from `source` to `target` within `max_hops`.

        This is the multi-hop answer vector search cannot produce: the concrete chain
        connecting a policy change to a loss cohort to the lesson that warned about it.
        """
        results: list[list[Edge]] = []
        stack: list[tuple[str, list[Edge], set[str]]] = [(source, [], {source})]

        while stack:
            current, path, visited = stack.pop()
            if len(path) >= max_hops:
                continue
            for edge, neighbor_id in self.neighbors(current, as_of=as_of):
                if neighbor_id in visited:
                    continue
                new_path = [*path, edge]
                if neighbor_id == target:
                    results.append(new_path)
                    continue
                stack.append((neighbor_id, new_path, visited | {neighbor_id}))

        return sorted(results, key=len)
