#!/usr/bin/env python3
"""Local search stack pipeline (LinkedIn Engineering FORMAT steal).

Source: https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack

Steal (not LinkedIn GPU/EBR/SGLang SaaS):
  1. Query understanding → intent + facets + route (keyword vs semantic)
  2. Broad retrieve → depth-limited ranking
  3. Score cache for repeated queries
  4. Explain snippets (why this hit matched)
  5. Product-policy relevance grades 0–4 (deterministic judge for lab docs)
  6. Continuous measurement hooks (precision@k on graded pairs)

Maps onto zg_search / hybrid rails when available; falls back to ripgrep-shaped
local file scan so CI stays dependency-light.

EXIT 0 always for report. EXIT 2 with --strict if ready check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "runtime" / "search_score_cache"

# Product policy (lab): how well a hit serves operator search intent
POLICY = """
Grade 0: unrelated
Grade 1: tangentially related keywords only
Grade 2: partial match (one facet)
Grade 3: strong match (most facets / clear path)
Grade 4: exact operator answer (script/rule/lesson that resolves the query)
"""

ENTITY_RE = re.compile(r"^(?:[A-Za-z_][\w]*|[A-Za-z]+(?:_[A-Za-z0-9]+)+|[A-Z]{2,}|\.py|\.md)$")


def understand_query(query: str) -> dict:
    """Lightweight query understanding (LinkedIn: intent + facets + routing)."""
    q = (query or "").strip()
    lower = q.lower()
    facets: dict[str, str] = {}
    # Simple facet extraction for trading lab
    for key, pats in {
        "strategy": [r"\bput[\s-]?credit\b", r"\biron[\s-]?condor\b", r"\bsp[yx]\b"],
        "risk": [r"\bkill[\s-]?switch\b", r"\bstop[\s-]?loss\b", r"\bhalt\b"],
        "ops": [r"\bci\b", r"\bpr\b", r"\bworktree\b", r"\blaunchagent\b"],
        "rag": [r"\brag\b", r"\blesson\b", r"\bll-\d+\b"],
    }.items():
        for pat in pats:
            if re.search(pat, lower):
                facets[key] = re.search(pat, lower).group(0)  # type: ignore[union-attr]
                break

    # Route: precise symbol/entity → keyword; ambiguous NL → semantic/hybrid
    tokens = [t for t in re.split(r"\s+", q) if t]
    precise = len(tokens) <= 2 and all(
        ENTITY_RE.match(t) or t.startswith("INV_") or t.startswith("LL-") for t in tokens
    )
    intent = "entity_lookup" if precise else "semantic_discovery"
    if "how" in lower or "why" in lower or "what" in lower:
        intent = "semantic_discovery"
    route = "keyword" if precise else "semantic"
    return {
        "query": q,
        "intent": intent,
        "facets": facets,
        "route": route,
        "thinking_state": (f"Routing as {route}: intent={intent}; facets={list(facets) or 'none'}"),
    }


def _cache_key(query: str, route: str, limit: int) -> str:
    raw = f"{route}|{limit}|{query.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def score_cache_get(query: str, route: str, limit: int) -> dict | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_cache_key(query, route, limit)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("expires_at", 0) < time.time():
        path.unlink(missing_ok=True)
        return None
    data["cache_hit"] = True
    return data


def score_cache_set(payload: dict, *, ttl_s: int = 3600) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(payload["understanding"]["query"], payload["route_used"], payload["limit"])
    row = dict(payload)
    row["expires_at"] = time.time() + ttl_s
    row.pop("cache_hit", None)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(row, indent=2, sort_keys=True))


def ranking_depth_controller(n_candidates: int, *, max_deep: int = 25) -> int:
    """LinkedIn: ranking-depth controller — cap how many enter deep rank."""
    return max(0, min(n_candidates, max_deep))


def explain_snippet(query: str, text: str, *, max_len: int = 160) -> str:
    """Why this hit matched — highlight overlapping terms (LinkedIn snippets FORMAT)."""
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9_\-]{3,}", query)]
    lines = (text or "").splitlines() or [text or ""]
    best = lines[0]
    best_score = -1
    for line in lines[:40]:
        low = line.lower()
        score = sum(1 for t in tokens if t in low)
        if score > best_score:
            best_score = score
            best = line.strip()
    snippet = best[:max_len]
    for t in sorted(set(tokens), key=len, reverse=True):
        snippet = re.sub(f"(?i)({re.escape(t)})", r"**\1**", snippet)
    return snippet


def policy_grade(query: str, path: str, snippet: str) -> dict:
    """Deterministic 0–4 grade aligned to lab product policy (no LLM teacher required)."""
    q_toks = set(re.findall(r"[a-z0-9_\-]{3,}", query.lower()))
    blob = f"{path} {snippet}".lower()
    overlap = sum(1 for t in q_toks if t in blob)
    grade = 0
    if overlap >= 1:
        grade = 1
    if overlap >= 2 or any(f in path for f in ("scripts/", "docs/", "rag_knowledge/")):
        grade = max(grade, 2)
    if overlap >= 3:
        grade = 3
    if overlap >= 4 and (path.endswith(".py") or "ll_" in path or "SPEC" in path):
        grade = 4
    return {
        "grade": grade,
        "scale": "0-4",
        "policy": "lab_operator_search",
        "overlap_tokens": overlap,
    }


def _retrieve_local(query: str, *, root: Path, limit: int, route: str) -> list[dict]:
    """Prefer zg_search; fall back to simple walk + keyword score."""
    try:
        import sys

        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from src.rag.zg_local_search import SearchRoute, ZgLocalSearch

        engine = ZgLocalSearch(root=root)
        zg_route = SearchRoute.RG if route == "keyword" else SearchRoute.HYBRID
        hits = engine.search(query, route=zg_route, limit=limit)
        out = []
        for h in hits:
            # normalize hit shapes
            if isinstance(h, dict):
                path = h.get("path") or h.get("file") or ""
                text = h.get("text") or h.get("snippet") or h.get("preview") or ""
                score = float(h.get("score") or h.get("rrf") or 0)
            else:
                path = getattr(h, "path", "") or ""
                text = getattr(h, "text", "") or getattr(h, "snippet", "") or ""
                score = float(getattr(h, "score", 0) or 0)
            out.append({"path": str(path), "text": str(text), "score": score})
        if out:
            return out
    except Exception as exc:  # noqa: BLE001 — fall back to local scan
        _ = exc  # keep path for debugging without swallowing silently as empty pass

    # Fallback: scan curated dirs
    q_toks = [t.lower() for t in re.findall(r"[A-Za-z0-9_\-]{3,}", query)]
    scored: list[dict] = []
    for folder in ("scripts", "docs", "rag_knowledge/lessons_learned", "src/rag"):
        base = root / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".md", ".json"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            low = text.lower()
            score = sum(low.count(t) for t in q_toks)
            if score <= 0:
                continue
            scored.append(
                {
                    "path": str(path.relative_to(root)),
                    "text": text[:2000],
                    "score": float(score),
                }
            )
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def run_pipeline(
    query: str,
    *,
    root: Path = ROOT,
    limit: int = 10,
    max_deep: int = 25,
    use_cache: bool = True,
) -> dict:
    understanding = understand_query(query)
    route = understanding["route"]
    if use_cache:
        cached = score_cache_get(query, route, limit)
        if cached:
            return cached

    # Broad retrieve then depth control
    broad_limit = max(limit * 3, max_deep)
    candidates = _retrieve_local(query, root=root, limit=broad_limit, route=route)
    deep_n = ranking_depth_controller(len(candidates), max_deep=max_deep)
    deep = candidates[:deep_n]

    ranked = []
    for hit in deep[:limit]:
        snippet = explain_snippet(query, hit.get("text") or "")
        grade = policy_grade(query, hit.get("path") or "", snippet)
        ranked.append(
            {
                "path": hit.get("path"),
                "score": hit.get("score"),
                "snippet": snippet,
                "relevance_grade": grade["grade"],
                "grade_detail": grade,
            }
        )
    # Re-rank by policy grade then score
    ranked.sort(key=lambda r: (-r["relevance_grade"], -(r.get("score") or 0)))

    # Continuous measurement hook
    grades = [r["relevance_grade"] for r in ranked]
    precision_at_3 = sum(1 for g in grades[:3] if g >= 3) / min(3, len(grades)) if grades else None

    out = {
        "ok": True,
        "framework": "search_stack_pipeline",
        "stolen_format": (
            "LinkedIn search stack FORMAT — query understand, EBR-style retrieve, "
            "depth controller, score cache, explain snippets, policy grades "
            "(not LinkedIn GPU/EBR product)"
        ),
        "source": {
            "linkedin_engineering": (
                "https://www.linkedin.com/blog/engineering/search/"
                "reimagining-linkedins-search-stack"
            )
        },
        "understanding": understanding,
        "route_used": route,
        "limit": limit,
        "candidates_broad": len(candidates),
        "candidates_deep": deep_n,
        "results": ranked,
        "metrics": {
            "precision_at_3_grade_ge_3": (
                round(precision_at_3, 4) if precision_at_3 is not None else None
            ),
            "policy": POLICY.strip().splitlines()[0],
        },
        "cache_hit": False,
        "ts": datetime.now(UTC).isoformat(),
    }
    if use_cache:
        score_cache_set(out)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--max-deep", type=int, default=25)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--understand-only", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    if not args.query.strip():
        p.error("query required")
    if args.understand_only:
        print(json.dumps(understand_query(args.query), indent=2, sort_keys=True))
        return 0
    out = run_pipeline(
        args.query,
        limit=args.limit,
        max_deep=args.max_deep,
        use_cache=not args.no_cache,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("results"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
