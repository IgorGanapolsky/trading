"""Deterministic operator task graph with selection receipts.

FORMAT steal from DoorDash Flux (InfoQ 2026-09-08): cloud agents run many
engineering tasks through a graph. We keep a tiny local DAG of *operator*
harness packs (from jit_harness) with prerequisite edges and JSON receipts.
We do **not** clone Flux, run 130k cloud agents, or auto-submit trades.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.ops.jit_harness import TaskClass, select_harness


@dataclass(frozen=True)
class GraphNode:
    id: str
    task_class: str
    requires: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["requires"] = list(self.requires)
        return d


# Fixed operator graphs — not model-generated.
_GRAPHS: dict[str, tuple[GraphNode, ...]] = {
    "dry_run_readiness": (
        GraphNode(
            id="status",
            task_class=TaskClass.STATUS.value,
            requires=(),
            description="Confirm kill switch + account status",
        ),
        GraphNode(
            id="inventory",
            task_class=TaskClass.INVENTORY.value,
            requires=("status",),
            description="Audit open inventory before new risk",
        ),
        GraphNode(
            id="dry_run",
            task_class=TaskClass.DRY_RUN.value,
            requires=("inventory",),
            description="Paper put-credit dry-run plan",
        ),
    ),
    "pr_hygiene": (
        GraphNode(
            id="status",
            task_class=TaskClass.STATUS.value,
            requires=(),
            description="Read-only system status before merges",
        ),
        GraphNode(
            id="pr_hygiene",
            task_class=TaskClass.PR_HYGIENE.value,
            requires=("status",),
            description="Inspect/merge ready PRs",
        ),
    ),
    "residual_exit": (
        GraphNode(
            id="status",
            task_class=TaskClass.STATUS.value,
            requires=(),
            description="Confirm IC entries remain killed",
        ),
        GraphNode(
            id="residual_ic",
            task_class=TaskClass.RESIDUAL_IC.value,
            requires=("status",),
            description="Residual IC exit-only dry-run",
        ),
    ),
}


@dataclass(frozen=True)
class GraphPlan:
    graph_id: str
    nodes: tuple[GraphNode, ...]
    order: tuple[str, ...]
    packs: dict[str, dict[str, Any]]
    ok: bool
    failing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "order": list(self.order),
            "nodes": [n.to_dict() for n in self.nodes],
            "packs": self.packs,
            "ok": self.ok,
            "failing": list(self.failing),
        }


def list_graphs() -> list[str]:
    return sorted(_GRAPHS)


def _topo(nodes: tuple[GraphNode, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    by_id = {n.id: n for n in nodes}
    failing: list[str] = []
    for n in nodes:
        for req in n.requires:
            if req not in by_id:
                failing.append(f"missing_dependency:{n.id}->{req}")
    if failing:
        return (), tuple(failing)

    pending = set(by_id)
    done: list[str] = []
    while pending:
        ready = [nid for nid in sorted(pending) if all(r in done for r in by_id[nid].requires)]
        if not ready:
            return (), ("cycle_or_unsatisfiable",)
        pick = ready[0]
        done.append(pick)
        pending.remove(pick)
    return tuple(done), ()


def plan_graph(graph_id: str) -> GraphPlan:
    """Resolve harness packs for each node in topological order."""

    nodes = _GRAPHS.get(graph_id)
    if nodes is None:
        return GraphPlan(
            graph_id=graph_id,
            nodes=(),
            order=(),
            packs={},
            ok=False,
            failing=("unknown_graph",),
        )
    order, failing = _topo(nodes)
    packs: dict[str, dict[str, Any]] = {}
    if not failing:
        for nid in order:
            node = next(n for n in nodes if n.id == nid)
            # Prompt shaped so classifier returns the intended class.
            prompt = {
                TaskClass.STATUS.value: "account status health kill switch",
                TaskClass.INVENTORY.value: "audit open inventory unclean",
                TaskClass.DRY_RUN.value: "put credit dry-run plan",
                TaskClass.PR_HYGIENE.value: "merge ready PRs and fix CI",
                TaskClass.RESIDUAL_IC.value: "residual IC exit plan",
            }.get(node.task_class, node.task_class)
            pack = select_harness(prompt)
            if pack.task_class.value != node.task_class:
                failing = failing + (f"pack_mismatch:{nid}:{pack.task_class.value}",)
            packs[nid] = {
                "task_class": pack.task_class.value,
                "token_budget_hint": pack.token_budget_hint,
                "paper_only": pack.paper_only,
                "actions": list(pack.actions),
                "forbid_n": len(pack.forbid),
            }
    return GraphPlan(
        graph_id=graph_id,
        nodes=nodes,
        order=order,
        packs=packs,
        ok=not failing,
        failing=tuple(failing),
    )


def write_receipt(plan: GraphPlan, path: Path | None = None) -> dict[str, Any]:
    """Append a flux graph receipt (eval/archive), not a trade."""

    payload = plan.to_dict()
    payload["recorded_at"] = datetime.now(UTC).isoformat()
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["receipt_hash"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload
