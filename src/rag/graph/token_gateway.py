"""TokenGuard — hard pre-synthesis context budget.

Multi-hop graph extractions inflate token costs. This gateway trims paths,
drops low-weight metadata, and can halt if context still exceeds budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token). No tokenizer dependency."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass
class TokenGuardResult:
    allowed: bool
    estimated_tokens: int
    max_tokens: int
    trimmed_paths: int
    trimmed_vector_hits: int
    context_text: str
    halt_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "estimated_tokens": self.estimated_tokens,
            "max_tokens": self.max_tokens,
            "trimmed_paths": self.trimmed_paths,
            "trimmed_vector_hits": self.trimmed_vector_hits,
            "halt_reason": self.halt_reason,
            "context_chars": len(self.context_text),
            "metadata": self.metadata,
        }


def _path_line(path: dict[str, Any]) -> str:
    nodes = path.get("node_ids") or []
    rels = path.get("rels") or []
    parts: list[str] = []
    for i, nid in enumerate(nodes):
        parts.append(str(nid))
        if i < len(rels):
            parts.append(f"--{rels[i]}-->")
    score = path.get("score")
    body = " ".join(parts)
    if score is not None:
        return f"[path score={float(score):.3f}] {body}"
    return f"[path] {body}"


def _node_line(node: dict[str, Any]) -> str:
    nid = node.get("id", "?")
    ntype = node.get("type", "?")
    label = node.get("label", "")
    props = node.get("properties") or {}
    # Drop bulky / low-value keys for prompt hygiene
    skip = {"snippet", "summary", "payload_keys", "evidence", "hybrid_leaf"}
    slim = {k: v for k, v in props.items() if k not in skip and v is not None}
    # Keep short snippet separately if present
    snippet = props.get("snippet") or props.get("summary") or ""
    if isinstance(snippet, str) and len(snippet) > 280:
        snippet = snippet[:277] + "..."
    bits = [f"- ({ntype}) {nid}: {label}"]
    if slim:
        bits.append(f"  props={slim}")
    if snippet:
        bits.append(f"  note={snippet}")
    return "\n".join(bits)


def _vector_line(hit: dict[str, Any]) -> str:
    lid = hit.get("id") or hit.get("lesson_id") or hit.get("file") or "doc"
    title = hit.get("title") or ""
    score = hit.get("score")
    snippet = hit.get("snippet") or hit.get("content") or hit.get("prevention") or ""
    if isinstance(snippet, str) and len(snippet) > 320:
        snippet = snippet[:317] + "..."
    score_s = f" score={float(score):.3f}" if score is not None else ""
    return f"- [vector{score_s}] {lid}: {title}\n  {snippet}".rstrip()


def apply_token_guard(
    *,
    query: str,
    intent: str,
    route_reason: str,
    paths: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    vector_hits: list[dict[str, Any]] | None = None,
    max_tokens: int = 1800,
    hard_max_tokens: int = 3200,
    max_paths: int = 12,
    max_nodes: int = 20,
    max_vector_hits: int = 5,
) -> TokenGuardResult:
    """Assemble and trim context under token budgets.

    Parameters
    ----------
    max_tokens:
        Soft budget — trim until under this.
    hard_max_tokens:
        Hard halt — if still over after aggressive trim, ``allowed=False``.
    """
    vector_hits = list(vector_hits or [])
    # Sort by score descending when present
    paths_sorted = sorted(paths, key=lambda p: float(p.get("score") or 0.0), reverse=True)
    nodes_sorted = list(nodes)
    vectors_sorted = sorted(
        vector_hits, key=lambda h: float(h.get("score") or 0.0), reverse=True
    )

    keep_paths = paths_sorted[:max_paths]
    keep_nodes = nodes_sorted[:max_nodes]
    keep_vectors = vectors_sorted[:max_vector_hits]
    trimmed_paths = max(0, len(paths_sorted) - len(keep_paths))
    trimmed_vectors = max(0, len(vectors_sorted) - len(keep_vectors))

    def build(paths_in: list, nodes_in: list, vectors_in: list) -> str:
        sections = [
            "# Graph RAG context",
            f"Query: {query}",
            f"Intent: {intent}",
            f"Route: {route_reason}",
            "",
            "## Graph paths",
        ]
        if paths_in:
            sections.extend(_path_line(p) for p in paths_in)
        else:
            sections.append("(none)")
        sections.append("")
        sections.append("## Graph nodes")
        if nodes_in:
            sections.extend(_node_line(n) for n in nodes_in)
        else:
            sections.append("(none)")
        if vectors_in:
            sections.append("")
            sections.append("## Vector / lesson fusion")
            sections.extend(_vector_line(v) for v in vectors_in)
        sections.append("")
        sections.append(
            "Constraints: paper-only validation; never claim edge without paired ledger n>=30."
        )
        return "\n".join(sections)

    text = build(keep_paths, keep_nodes, keep_vectors)
    tokens = estimate_tokens(text)

    # Progressive trim if over soft budget
    while tokens > max_tokens and (keep_paths or keep_vectors or len(keep_nodes) > 3):
        if keep_vectors:
            keep_vectors.pop()
            trimmed_vectors += 1
        elif len(keep_paths) > 2:
            keep_paths.pop()
            trimmed_paths += 1
        elif len(keep_nodes) > 3:
            keep_nodes.pop()
        else:
            break
        text = build(keep_paths, keep_nodes, keep_vectors)
        tokens = estimate_tokens(text)

    # Aggressive: strip node props notes if still high
    if tokens > max_tokens:
        slim_nodes = []
        for n in keep_nodes:
            props = dict(n.get("properties") or {})
            props.pop("snippet", None)
            props.pop("summary", None)
            slim_nodes.append({**n, "properties": props})
        keep_nodes = slim_nodes
        text = build(keep_paths, keep_nodes, keep_vectors)
        tokens = estimate_tokens(text)

    allowed = tokens <= hard_max_tokens
    halt = None if allowed else (
        f"context estimated_tokens={tokens} exceeds hard_max_tokens={hard_max_tokens}"
    )
    if not allowed:
        text = (
            f"# Graph RAG HALTED\nQuery: {query}\nReason: {halt}\n"
            "Reduce max_hops or narrow intent before synthesis."
        )
        tokens = estimate_tokens(text)

    return TokenGuardResult(
        allowed=allowed,
        estimated_tokens=tokens,
        max_tokens=max_tokens,
        trimmed_paths=trimmed_paths,
        trimmed_vector_hits=trimmed_vectors,
        context_text=text,
        halt_reason=halt,
        metadata={
            "paths_kept": len(keep_paths),
            "nodes_kept": len(keep_nodes),
            "vector_hits_kept": len(keep_vectors),
            "hard_max_tokens": hard_max_tokens,
        },
    )
