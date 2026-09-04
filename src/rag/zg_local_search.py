"""zg-style local-first search: ripgrep + BM25/FTS + vector behind one interface.

Steals the high-ROI mechanics from Qwen/zvec-grep (zg), not the npm package:

* Four routes: ``hybrid`` (default), ``fts``, ``vector``, ``rg``
* Reciprocal Rank Fusion (RRF) when combining ranked lists
* Managed ripgrep works without an embedding index
* Compact path:line evidence for agents (fewer tokens)
* Local-first: no remote embeddings; vector is optional/offline only

See docs/ZG_LOCAL_SEARCH.md and MarkTechPost 2026-09-02 on zg (zvec-grep).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess  # nosec B404 — managed local ripgrep only; argv list, never shell
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable

from src.rag.hybrid_retriever import HybridRAGRetriever
from src.rag.query_rewriter import RAGQueryRewriter

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Default include globs for managed ripgrep (matched relative to search root).
# Prefer extension/path fragments — ripgrep does not treat `src/**/*.py` as a
# rooted path prefix the way shell globs do.
DEFAULT_RG_GLOBS = (
    "*.py",
    "*.md",
    "*.json",
    "*.yml",
    "*.yaml",
    "!**/.venv/**",
    "!**/node_modules/**",
    "!**/.git/**",
    "!**/__pycache__/**",
)


class SearchRoute(StrEnum):
    HYBRID = "hybrid"
    FTS = "fts"
    VECTOR = "vector"
    RG = "rg"


@dataclass(frozen=True)
class EvidenceHit:
    """Compact, source-linked hit suitable for agent context."""

    id: str
    path: str
    line: int | None
    preview: str
    score: float
    route: str
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compact_line(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        title = f" {self.title}" if self.title else ""
        preview = self.preview.replace("\n", " ").strip()
        if len(preview) > 160:
            preview = preview[:157] + "..."
        return f"[{self.route} {self.score:.4f}] {loc}{title} — {preview}"


VectorFn = Callable[[str, int], list[dict[str, Any]]]
FtsFn = Callable[[str, int], list[dict[str, Any]]]


def _canonical_doc_id(raw_id: str) -> str:
    """Unify lesson:/LL-/path-ish IDs so RRF can fuse cross-route duplicates."""
    s = (raw_id or "").strip()
    if not s:
        return s
    lower = s.lower()
    if lower.startswith("lesson:"):
        s = s.split(":", 1)[1]
    # Strip common path wrappers for lesson markdown files.
    if "/" in s and s.lower().endswith(".md"):
        stem = Path(s).stem
        # ll_301_foo / LL-301_foo → prefer lesson token when present
        m = re.search(r"(LL[-_]?\d+)", stem, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper().replace("_", "-")
        return stem
    m = re.fullmatch(r"(?i)ll[-_]?(\d+)", s)
    if m:
        return f"LL-{m.group(1)}"
    return s


def _normalize_item(item: dict[str, Any], *, default_route: str) -> dict[str, Any]:
    path = str(item.get("path") or item.get("file") or item.get("source") or item.get("id") or "")
    preview = str(item.get("snippet") or item.get("content") or item.get("preview") or "")
    line = item.get("line")
    try:
        line_i = int(line) if line is not None else None
    except (TypeError, ValueError):
        line_i = None
    score = item.get("score")
    try:
        score_f = float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        score_f = 0.0
    raw_id = str(item.get("id") or path or f"{default_route}:{preview[:40]}")
    return {
        "id": _canonical_doc_id(raw_id) or raw_id,
        "path": path,
        "line": line_i,
        "preview": preview[:500],
        "score": score_f,
        "route": str(item.get("route") or default_route),
        "title": str(item.get("title") or ""),
        "metadata": dict(item.get("metadata") or {}),
    }


def _looks_like_symbol(query: str) -> bool:
    """Heuristic: exact identifier / path / regex → prefer rg anchors in hybrid."""
    q = query.strip()
    if not q:
        return False
    if any(ch in q for ch in ("*", "^", "$", "\\", "/", ".")):
        # path-ish or regex-ish, but still allow multi-word NL
        if " " not in q and len(q) <= 80:
            return True
    # CamelCase / snake_case / SCREAMING_SNAKE without spaces
    return " " not in q and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{2,}", q))


class ZgLocalSearch:
    """One local-first search layer with four retrieval routes."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        k_rrf: float = 60.0,
        fts_fn: FtsFn | None = None,
        vector_fn: VectorFn | None = None,
        rg_bin: str | None = None,
        rewrite_queries: bool = True,
    ) -> None:
        self.root = Path(root) if root else PROJECT_ROOT
        self.retriever = HybridRAGRetriever(k_rrf=k_rrf)
        self.rewriter = RAGQueryRewriter() if rewrite_queries else None
        self._fts_fn = fts_fn
        self._vector_fn = vector_fn
        self._rg_bin = rg_bin or shutil.which("rg") or "rg"

    def search(
        self,
        query: str,
        *,
        route: SearchRoute | str = SearchRoute.HYBRID,
        limit: int = 10,
        globs: Iterable[str] | None = None,
        fuse_rg: bool | None = None,
    ) -> list[EvidenceHit]:
        q = (query or "").strip()
        if not q:
            return []

        if isinstance(route, SearchRoute):
            route_e = route
        else:
            route_e = SearchRoute(str(route).strip().lower())
        expanded = q
        if self.rewriter is not None and route_e != SearchRoute.RG:
            expanded = self.rewriter.rewrite(q).expanded_query

        if route_e == SearchRoute.FTS:
            return self._to_hits(self._run_fts(expanded, limit), route="fts")[:limit]
        if route_e == SearchRoute.VECTOR:
            return self._to_hits(self._run_vector(expanded, limit), route="vector")[:limit]
        if route_e == SearchRoute.RG:
            return self._to_hits(self._run_rg(q, limit=limit, globs=globs), route="rg")[:limit]

        # hybrid: FTS + vector (+ optional rg for symbol-like queries)
        fts = self._run_fts(expanded, max(limit * 3, 15))
        vec = self._run_vector(expanded, max(limit * 3, 15))
        include_rg = fuse_rg if fuse_rg is not None else _looks_like_symbol(q)
        rg_hits = self._run_rg(q, limit=max(limit * 2, 10), globs=globs) if include_rg else []

        merged = self.retriever.rrf_merge_multi(
            {
                "fts": fts,
                "vector": vec,
                "rg": rg_hits,
            },
            top_n=limit,
        )
        return merged

    def format_compact(self, hits: list[EvidenceHit]) -> str:
        if not hits:
            return "(no hits)"
        return "\n".join(h.compact_line() for h in hits)

    # --- route runners -------------------------------------------------

    def _run_fts(self, query: str, limit: int) -> list[dict[str, Any]]:
        if self._fts_fn is not None:
            try:
                return [_normalize_item(x, default_route="fts") for x in self._fts_fn(query, limit)]
            except Exception as exc:  # noqa: BLE001 — route must fail soft
                logger.warning("fts_fn failed: %s", exc)
                return []
        try:
            from src.rag.unified_search import UnifiedSearch

            search = UnifiedSearch()
            search.build_index()
            raw = search.search(query, top_k=limit)
            out: list[dict[str, Any]] = []
            for item in raw:
                out.append(
                    _normalize_item(
                        {
                            "id": item.get("id"),
                            "path": item.get("id"),
                            "title": item.get("title"),
                            "snippet": item.get("snippet") or item.get("content", ""),
                            "score": item.get("score", 0.0),
                            "metadata": {
                                "source_type": item.get("source_type"),
                                **(item.get("metadata") or {}),
                            },
                        },
                        default_route="fts",
                    )
                )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("UnifiedSearch FTS failed: %s", exc)
            return []

    def _run_vector(self, query: str, limit: int) -> list[dict[str, Any]]:
        if self._vector_fn is not None:
            try:
                return [
                    _normalize_item(x, default_route="vector")
                    for x in self._vector_fn(query, limit)
                ]
            except Exception as exc:  # noqa: BLE001
                logger.warning("vector_fn failed: %s", exc)
                return []
        # Optional local LanceDB / LessonsLearnedRAG — soft fail when unavailable.
        # Probe lancedb first so we do not pull HF embedding weights on a miss.
        try:
            import lancedb  # noqa: F401
        except ImportError:
            logger.debug("vector route skipped: lancedb not installed")
            return []
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            if getattr(rag, "lancedb_rag", None) is None:
                return []
            raw = rag._query_lancedb(query, top_k=limit)  # noqa: SLF001 — local optional path
            return [
                _normalize_item(
                    {
                        "id": r.get("id"),
                        "path": r.get("file") or r.get("id"),
                        "title": r.get("title"),
                        "snippet": r.get("snippet") or r.get("content", ""),
                        "score": r.get("score", 0.0),
                        "metadata": {"severity": r.get("severity")},
                    },
                    default_route="vector",
                )
                for r in raw
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("vector route unavailable: %s", exc)
            return []

    def _run_rg(
        self,
        pattern: str,
        *,
        limit: int,
        globs: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Managed ripgrep: exhaustive literal/regex, no index required.

        Falls back to a pure-Python line scan when the ``rg`` binary is absent
        (GitHub-hosted CI runners often lack ripgrep).
        """
        rg = self._rg_bin
        if shutil.which(rg) or Path(rg).exists():
            hits = self._run_rg_binary(pattern, limit=limit, globs=globs)
            if hits:
                return hits
            # Binary present but no matches — do not invent hits.
            return []
        logger.info("ripgrep binary not found (%s); using Python line-scan fallback", rg)
        return self._run_rg_python(pattern, limit=limit, globs=globs)

    def _run_rg_binary(
        self,
        pattern: str,
        *,
        limit: int,
        globs: Iterable[str] | None,
    ) -> list[dict[str, Any]]:
        glob_args: list[str] = []
        for g in globs or DEFAULT_RG_GLOBS:
            glob_args.extend(["-g", g])

        # --max-count is per-file; keep it small and truncate globally in Python
        # so a large workspace does not buffer unbounded matches.
        cmd = [
            self._rg_bin,
            "--line-number",
            "--no-heading",
            "--color",
            "never",
            "--max-count",
            "1",
            *glob_args,
            "--",
            pattern,
            str(self.root),
        ]
        try:
            # argv list only (no shell); pattern is treated as a search string by rg.
            proc = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("rg failed: %s", exc)
            return []

        return self._parse_rg_stdout(proc.stdout or "", limit=limit)

    def _run_rg_python(
        self,
        pattern: str,
        *,
        limit: int,
        globs: Iterable[str] | None,
    ) -> list[dict[str, Any]]:
        """Bounded recursive text scan used when ripgrep is unavailable."""
        # Literal match by default — avoid catastrophic backtracking on caller patterns.
        regex = re.compile(re.escape(pattern))

        default_exts = {".py", ".md", ".json", ".yml", ".yaml"}
        include_exts: set[str] = set()
        for g in globs or ():
            if g.startswith("*.") and len(g) <= 10:
                include_exts.add(g[1:].lower())
        if not include_exts:
            include_exts = default_exts

        skip_dirs = {".git", ".venv", "node_modules", "__pycache__", ".tox", "dist", "build"}
        hits: list[dict[str, Any]] = []
        root = self.root
        for path in root.rglob("*"):
            if len(hits) >= limit:
                break
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix.lower() not in include_exts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # Match binary rg --max-count 1: at most one hit per file.
            for i, line in enumerate(text.splitlines(), 1):
                if not regex.search(line):
                    continue
                try:
                    rel = str(path.resolve().relative_to(root.resolve()))
                except ValueError:
                    rel = str(path)
                hits.append(
                    _normalize_item(
                        {
                            "id": f"rg:{rel}:{i}",
                            "path": rel,
                            "line": i,
                            "preview": line.strip(),
                            "score": 1.0 / (len(hits) + 1),
                            "title": "",
                        },
                        default_route="rg",
                    )
                )
                break
        return hits

    def _parse_rg_stdout(self, stdout: str, *, limit: int) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for raw_line in stdout.splitlines():
            if len(hits) >= limit:
                break
            m = re.match(r"^(.*?):(\d+):(.*)$", raw_line)
            if not m:
                continue
            path_s, line_s, text = m.group(1), m.group(2), m.group(3)
            try:
                rel = str(Path(path_s).resolve().relative_to(self.root.resolve()))
            except ValueError:
                rel = path_s
            hits.append(
                _normalize_item(
                    {
                        "id": f"rg:{rel}:{line_s}",
                        "path": rel,
                        "line": int(line_s),
                        "preview": text.strip(),
                        "score": 1.0 / (len(hits) + 1),
                        "title": "",
                    },
                    default_route="rg",
                )
            )
        return hits

    def _to_hits(self, items: list[dict[str, Any]], *, route: str) -> list[EvidenceHit]:
        out: list[EvidenceHit] = []
        for item in items:
            n = _normalize_item(item, default_route=route)
            out.append(
                EvidenceHit(
                    id=n["id"],
                    path=n["path"],
                    line=n["line"],
                    preview=n["preview"],
                    score=float(n["score"]),
                    route=n["route"],
                    title=n["title"],
                    metadata=n["metadata"],
                )
            )
        return out


def search(
    query: str,
    *,
    route: str = "hybrid",
    limit: int = 10,
    root: Path | None = None,
) -> list[EvidenceHit]:
    """Module-level convenience wrapper."""
    return ZgLocalSearch(root=root).search(query, route=route, limit=limit)
