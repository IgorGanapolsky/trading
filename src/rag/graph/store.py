"""SQLite temporal property graph store (stdlib-only).

Temporal edges: ``valid_from`` / ``valid_to`` (NULL valid_to = still active).
Sub-second BFS pathfinding for hop depths used in strategy research (1–3 hops).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from src.rag.graph.schema import EdgeRel, NodeType

DEFAULT_GRAPH_DB = Path(os.getenv("TRADING_GRAPH_RAG_DB", "data/rag/financial_graph.sqlite"))

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    label         TEXT NOT NULL DEFAULT '',
    properties    TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id            TEXT PRIMARY KEY,
    src           TEXT NOT NULL,
    dst           TEXT NOT NULL,
    rel           TEXT NOT NULL,
    weight        REAL NOT NULL DEFAULT 1.0,
    properties    TEXT NOT NULL DEFAULT '{}',
    valid_from    TEXT,
    valid_to      TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (src) REFERENCES nodes(id),
    FOREIGN KEY (dst) REFERENCES nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(rel);
CREATE INDEX IF NOT EXISTS idx_edges_temporal ON edges(valid_from, valid_to);
"""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    id: str
    src: str
    dst: str
    rel: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphPath:
    """A bounded walk through the graph."""

    node_ids: list[str]
    edge_ids: list[str]
    rels: list[str]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_ids": self.node_ids,
            "edge_ids": self.edge_ids,
            "rels": self.rels,
            "score": self.score,
            "hops": max(0, len(self.node_ids) - 1),
        }


class FinancialGraphStore:
    """Thread-safe SQLite property graph with temporal edge filters."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DEFAULT_GRAPH_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.executescript(_SCHEMA_SQL)
            conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def upsert_node(
        self,
        node_id: str,
        node_type: NodeType | str,
        label: str = "",
        properties: dict[str, Any] | None = None,
    ) -> GraphNode:
        ntype = node_type.value if isinstance(node_type, NodeType) else str(node_type)
        props = properties or {}
        now = _utc_now()
        with self._lock:
            conn = self._connect()
            existing = conn.execute(
                "SELECT id, created_at, properties FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if existing:
                merged = _loads(existing["properties"])
                merged.update(props)
                conn.execute(
                    """
                    UPDATE nodes
                    SET type = ?, label = ?, properties = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (ntype, label or node_id, _dumps(merged), now, node_id),
                )
                created = existing["created_at"]
                out_props = merged
            else:
                conn.execute(
                    """
                    INSERT INTO nodes (id, type, label, properties, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (node_id, ntype, label or node_id, _dumps(props), now, now),
                )
                created = now
                out_props = props
            conn.commit()
        return GraphNode(
            id=node_id,
            type=ntype,
            label=label or node_id,
            properties=out_props,
            created_at=created,
            updated_at=now,
        )

    def upsert_edge(
        self,
        src: str,
        dst: str,
        rel: EdgeRel | str,
        *,
        edge_id: str | None = None,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
        valid_from: str | None = None,
        valid_to: str | None = None,
        replace_active: bool = True,
    ) -> GraphEdge:
        """Upsert an edge. If replace_active, expire prior open edges for (src,dst,rel)."""
        r = rel.value if isinstance(rel, EdgeRel) else str(rel)
        now = _utc_now()
        eid = edge_id or f"e:{src}:{r}:{dst}:{uuid.uuid4().hex[:8]}"
        props = properties or {}
        with self._lock:
            conn = self._connect()
            # Ensure endpoints exist (lightweight stubs if missing)
            for nid in (src, dst):
                row = conn.execute("SELECT id FROM nodes WHERE id = ?", (nid,)).fetchone()
                if not row:
                    conn.execute(
                        """
                        INSERT INTO nodes (id, type, label, properties, created_at, updated_at)
                        VALUES (?, 'concept', ?, '{}', ?, ?)
                        """,
                        (nid, nid, now, now),
                    )
            if replace_active:
                conn.execute(
                    """
                    UPDATE edges
                    SET valid_to = ?
                    WHERE src = ? AND dst = ? AND rel = ?
                      AND (valid_to IS NULL OR valid_to = '')
                      AND id != ?
                    """,
                    (now, src, dst, r, eid),
                )
            existing = conn.execute("SELECT id FROM edges WHERE id = ?", (eid,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE edges
                    SET src = ?, dst = ?, rel = ?, weight = ?, properties = ?,
                        valid_from = ?, valid_to = ?
                    WHERE id = ?
                    """,
                    (src, dst, r, weight, _dumps(props), valid_from, valid_to, eid),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO edges
                        (id, src, dst, rel, weight, properties, valid_from, valid_to, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (eid, src, dst, r, weight, _dumps(props), valid_from, valid_to, now),
                )
            conn.commit()
        return GraphEdge(
            id=eid,
            src=src,
            dst=dst,
            rel=r,
            weight=weight,
            properties=props,
            valid_from=valid_from,
            valid_to=valid_to,
            created_at=now,
        )

    def expire_edge(self, edge_id: str, at: str | None = None) -> None:
        when = at or _utc_now()
        with self._lock:
            conn = self._connect()
            conn.execute("UPDATE edges SET valid_to = ? WHERE id = ?", (when, edge_id))
            conn.commit()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> GraphNode | None:
        with self._lock:
            conn = self._connect()
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            return None
        return self._row_to_node(row)

    def get_nodes_by_type(self, node_type: NodeType | str, limit: int = 500) -> list[GraphNode]:
        ntype = node_type.value if isinstance(node_type, NodeType) else str(node_type)
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                "SELECT * FROM nodes WHERE type = ? LIMIT ?",
                (ntype, limit),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def search_nodes(self, text: str, limit: int = 25) -> list[GraphNode]:
        """Case-insensitive substring match on id/label/properties."""
        q = f"%{text.lower()}%"
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                """
                SELECT * FROM nodes
                WHERE lower(id) LIKE ?
                   OR lower(label) LIKE ?
                   OR lower(properties) LIKE ?
                LIMIT ?
                """,
                (q, q, q, limit),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def neighbors(
        self,
        node_id: str,
        *,
        direction: str = "both",
        rels: Iterable[str | EdgeRel] | None = None,
        as_of: str | None = None,
        limit: int = 100,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        """Return (edge, other_node) pairs. direction: out|in|both."""
        rel_filter: list[str] | None = None
        if rels:
            rel_filter = [r.value if isinstance(r, EdgeRel) else str(r) for r in rels]

        # Fully parameterized queries — no user strings interpolated into SQL.
        base_select = (
            "SELECT e.*, n.id AS n_id, n.type AS n_type, n.label AS n_label, "
            "n.properties AS n_properties, n.created_at AS n_created, "
            "n.updated_at AS n_updated "
            "FROM edges e "
            "JOIN nodes n ON n.id = CASE WHEN e.src = ? THEN e.dst ELSE e.src END "
        )
        params: list[Any] = [node_id]

        if direction == "out":
            where = "WHERE e.src = ?"
            params.append(node_id)
        elif direction == "in":
            where = "WHERE e.dst = ?"
            params.append(node_id)
        else:
            where = "WHERE (e.src = ? OR e.dst = ?)"
            params.extend([node_id, node_id])

        if rel_filter:
            placeholders = ",".join("?" for _ in rel_filter)
            where += f" AND e.rel IN ({placeholders})"
            params.extend(rel_filter)

        if as_of:
            where += (
                " AND (e.valid_from IS NULL OR e.valid_from <= ?)"
                " AND (e.valid_to IS NULL OR e.valid_to = '' OR e.valid_to > ?)"
            )
            params.extend([as_of, as_of])
        else:
            where += " AND (e.valid_to IS NULL OR e.valid_to = '')"

        sql = base_select + where + " ORDER BY e.weight DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            conn = self._connect()
            rows = conn.execute(sql, params).fetchall()
        out: list[tuple[GraphEdge, GraphNode]] = []
        for row in rows:
            edge = self._row_to_edge(row)
            node = GraphNode(
                id=row["n_id"],
                type=row["n_type"],
                label=row["n_label"],
                properties=_loads(row["n_properties"]),
                created_at=row["n_created"],
                updated_at=row["n_updated"],
            )
            out.append((edge, node))
        return out

    def bfs_paths(
        self,
        seed_ids: list[str],
        *,
        max_hops: int = 2,
        max_paths: int = 40,
        as_of: str | None = None,
        prefer_rels: Iterable[str | EdgeRel] | None = None,
    ) -> list[GraphPath]:
        """Multi-source BFS collecting unique paths up to max_hops."""
        if not seed_ids:
            return []
        prefer = {(r.value if isinstance(r, EdgeRel) else str(r)) for r in (prefer_rels or [])}
        paths: list[GraphPath] = []
        seen_terminal: set[tuple[str, ...]] = set()

        for seed in seed_ids:
            # state: (node, path_nodes, path_edges, path_rels, score)
            queue: deque[tuple[str, list[str], list[str], list[str], float]] = deque()
            queue.append((seed, [seed], [], [], 1.0))
            visited_from_seed: set[str] = {seed}

            while queue and len(paths) < max_paths:
                node, pnodes, pedges, prels, score = queue.popleft()
                hops = len(pnodes) - 1
                if hops > 0:
                    key = tuple(pnodes)
                    if key not in seen_terminal:
                        seen_terminal.add(key)
                        paths.append(
                            GraphPath(
                                node_ids=list(pnodes),
                                edge_ids=list(pedges),
                                rels=list(prels),
                                score=score,
                            )
                        )
                if hops >= max_hops:
                    continue
                for edge, other in self.neighbors(node, direction="both", as_of=as_of, limit=50):
                    if other.id in visited_from_seed and other.id != seed:
                        # allow revisiting seed only; skip cycles
                        if other.id in pnodes:
                            continue
                    if other.id in pnodes:
                        continue
                    boost = 1.15 if edge.rel in prefer else 1.0
                    nscore = score * float(edge.weight) * boost
                    visited_from_seed.add(other.id)
                    queue.append(
                        (
                            other.id,
                            pnodes + [other.id],
                            pedges + [edge.id],
                            prels + [edge.rel],
                            nscore,
                        )
                    )

        paths.sort(key=lambda p: p.score, reverse=True)
        return paths[:max_paths]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            n_nodes = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
            n_edges = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
            active_edges = conn.execute(
                "SELECT COUNT(*) AS c FROM edges WHERE valid_to IS NULL OR valid_to = ''"
            ).fetchone()["c"]
            by_type = {
                row["type"]: row["c"]
                for row in conn.execute(
                    "SELECT type, COUNT(*) AS c FROM nodes GROUP BY type"
                ).fetchall()
            }
            by_rel = {
                row["rel"]: row["c"]
                for row in conn.execute(
                    "SELECT rel, COUNT(*) AS c FROM edges GROUP BY rel"
                ).fetchall()
            }
        return {
            "db_path": str(self.db_path),
            "nodes": n_nodes,
            "edges": n_edges,
            "active_edges": active_edges,
            "nodes_by_type": by_type,
            "edges_by_rel": by_rel,
        }

    def clear(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM edges")
            conn.execute("DELETE FROM nodes")
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> GraphNode:
        return GraphNode(
            id=row["id"],
            type=row["type"],
            label=row["label"],
            properties=_loads(row["properties"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"],
            src=row["src"],
            dst=row["dst"],
            rel=row["rel"],
            weight=float(row["weight"] or 1.0),
            properties=_loads(row["properties"]),
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            created_at=row["created_at"],
        )


def adjacency_summary(store: FinancialGraphStore, node_id: str, limit: int = 12) -> dict[str, Any]:
    """Compact neighbor summary for prompt assembly."""
    node = store.get_node(node_id)
    if not node:
        return {"id": node_id, "missing": True}
    neigh = store.neighbors(node_id, limit=limit)
    grouped: dict[str, list[str]] = defaultdict(list)
    for edge, other in neigh:
        grouped[edge.rel].append(f"{other.id} ({other.type})")
    return {
        "id": node.id,
        "type": node.type,
        "label": node.label,
        "properties": node.properties,
        "neighbors": dict(grouped),
    }
