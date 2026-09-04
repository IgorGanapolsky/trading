#!/usr/bin/env python3
"""Operator CLI for official Graphify-Labs/graphify (PyPI: graphifyy).

This is not a SQLite dump and not a cloned graph-database query language.
Retrieval is graph.json via query / path / explain. graph.html is visualization only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.rag.graphify.cli import (  # noqa: E402
    GraphifyCliError,
    extract_code,
    graphify_version,
    install_official,
    resolve_graphify_bin,
    run_explain,
    run_path,
    run_query,
)
from src.rag.graphify.contract import (  # noqa: E402
    OFFICIAL_CLI_NAME,
    OFFICIAL_PYPI_PACKAGE,
    OFFICIAL_REPO,
)
from src.rag.graphify.fuse import fuse_hits_with_graph  # noqa: E402
from src.rag.graphify.graph import (  # noqa: E402
    default_graph_path,
    load_code_graph,
)


def _graph_path(repo: Path, explicit: str | None) -> Path:
    return Path(explicit) if explicit else default_graph_path(repo)


def cmd_status(repo: Path, graph: Path) -> dict[str, Any]:
    binary = resolve_graphify_bin(repo)
    payload: dict[str, Any] = {
        "official_package": OFFICIAL_PYPI_PACKAGE,
        "official_cli": OFFICIAL_CLI_NAME,
        "official_repo": OFFICIAL_REPO,
        "binary": str(binary) if binary else None,
        "version": graphify_version(repo) if binary else "",
        "graph_json": str(graph),
        "graph_exists": graph.is_file(),
        "html_is_not_retrieval": True,
        "financial_graph_is_separate": True,
    }
    if graph.is_file():
        code_graph = load_code_graph(graph)
        payload["nodes"] = len(code_graph.nodes)
        payload["edges"] = len(code_graph.edges)
        payload["confidence_counts"] = code_graph.confidence_counts()
        payload["validity_window"] = None
    return payload


def cmd_query(repo: Path, graph: Path, question: str) -> dict[str, Any]:
    binary = resolve_graphify_bin(repo)
    if binary is not None and graph.is_file():
        completed = run_query(question, repo_root=repo, graph=graph)
        return {
            "mode": "cli",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    code_graph = load_code_graph(graph)
    return {"mode": "local", **code_graph.query(question)}


def cmd_path(repo: Path, graph: Path, start: str, goal: str) -> dict[str, Any]:
    binary = resolve_graphify_bin(repo)
    if binary is not None and graph.is_file():
        completed = run_path(start, goal, repo_root=repo, graph=graph)
        return {
            "mode": "cli",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    trail = load_code_graph(graph).shortest_path(start, goal)
    return {"mode": "local", "path": trail}


def cmd_explain(repo: Path, graph: Path, node: str) -> dict[str, Any]:
    binary = resolve_graphify_bin(repo)
    if binary is not None and graph.is_file():
        completed = run_explain(node, repo_root=repo, graph=graph)
        return {
            "mode": "cli",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    return {"mode": "local", "explain": load_code_graph(graph).explain(node)}


def cmd_fuse(graph: Path, question: str, hits_json: str | None) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    if hits_json:
        loaded = json.loads(Path(hits_json).read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            hits = [item for item in loaded if isinstance(item, dict)]
    else:
        hits = [{"id": question, "title": question, "file": ""}]
    code_graph = load_code_graph(graph) if graph.is_file() else None
    return fuse_hits_with_graph(hits, code_graph)


def _common() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", type=Path, default=_REPO_ROOT)
    common.add_argument(
        "--graph", help="path to graph.json (default <repo>/graphify-out/graph.json)"
    )
    common.add_argument("--json", action="store_true", dest="as_json")
    return common


def _parser() -> argparse.ArgumentParser:
    common = _common()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", parents=[common], help="official CLI + graph.json readiness")
    sub.add_parser("install", parents=[common], help="uv tool install graphifyy")
    extract = sub.add_parser(
        "extract", parents=[common], help="graphify extract --code-only --no-cluster"
    )
    extract.add_argument("target", nargs="?", default=".")
    query = sub.add_parser("query", parents=[common], help="graphify query against graph.json")
    query.add_argument("question")
    path_cmd = sub.add_parser("path", parents=[common], help="graphify path A B")
    path_cmd.add_argument("start")
    path_cmd.add_argument("goal")
    explain = sub.add_parser("explain", parents=[common], help="graphify explain NODE")
    explain.add_argument("node")
    fuse = sub.add_parser("fuse", parents=[common], help="search hits + 1-2 hop graph traversal")
    fuse.add_argument("question")
    fuse.add_argument("--hits", help="JSON list of search hits")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = args.repo.resolve()
    graph = _graph_path(repo, args.graph)
    try:
        if args.command == "status":
            payload: Any = cmd_status(repo, graph)
        elif args.command == "install":
            completed = install_official(repo)
            payload = {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "package": OFFICIAL_PYPI_PACKAGE,
            }
        elif args.command == "extract":
            completed = extract_code(repo, target=args.target)
            payload = {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        elif args.command == "query":
            payload = cmd_query(repo, graph, args.question)
        elif args.command == "path":
            payload = cmd_path(repo, graph, args.start, args.goal)
        elif args.command == "explain":
            payload = cmd_explain(repo, graph, args.node)
        else:
            payload = cmd_fuse(graph, args.question, args.hits)
    except (GraphifyCliError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.as_json or isinstance(payload, dict):
        text = (
            payload if isinstance(payload, str) else json.dumps(payload, indent=2, sort_keys=True)
        )
        print(text if isinstance(text, str) else json.dumps(text))
        if isinstance(payload, dict) and payload.get("returncode") not in (None, 0):
            return int(payload["returncode"])
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
