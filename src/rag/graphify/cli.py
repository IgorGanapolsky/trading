"""Resolve and invoke the official Graphify CLI (package graphifyy)."""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import Sequence

from src.rag.graphify.contract import OFFICIAL_CLI_NAME, OFFICIAL_PYPI_PACKAGE

_HOME = Path.home()
_CANDIDATES = (
    _HOME / ".local" / "bin" / OFFICIAL_CLI_NAME,
    Path("/opt/homebrew/bin") / OFFICIAL_CLI_NAME,
    Path("/usr/local/bin") / OFFICIAL_CLI_NAME,
)


class GraphifyCliError(RuntimeError):
    """Official graphify binary missing or command failed."""


def resolve_graphify_bin(repo_root: str | Path | None = None) -> Path | None:
    """Return the official ``graphify`` executable if present."""
    if repo_root is not None:
        local = Path(repo_root) / ".graphify-venv" / "bin" / OFFICIAL_CLI_NAME
        if local.is_file():
            return local
    env_bin = os.environ.get("GRAPHIFY_BIN")
    if env_bin:
        path = Path(env_bin)
        if path.is_file():
            return path
    for candidate in _CANDIDATES:
        if candidate.is_file():
            return candidate
    which = shutil.which(OFFICIAL_CLI_NAME)
    return Path(which) if which else None


def graphify_version(repo_root: str | Path | None = None) -> str:
    binary = resolve_graphify_bin(repo_root)
    if binary is None:
        return ""
    completed = _run([str(binary), "--version"], timeout=20)
    if completed.returncode != 0:
        return ""
    return (completed.stdout or completed.stderr).strip()


def install_official(repo_root: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    """Install the official PyPI package ``graphifyy`` via uv tool or pipx."""
    uv = shutil.which("uv")
    if uv:
        return _run([uv, "tool", "install", OFFICIAL_PYPI_PACKAGE], timeout=180)
    pipx = shutil.which("pipx")
    if pipx:
        return _run([pipx, "install", OFFICIAL_PYPI_PACKAGE], timeout=180)
    raise GraphifyCliError(
        "Need uv or pipx to install graphifyy "
        f"(official package {OFFICIAL_PYPI_PACKAGE}; CLI {OFFICIAL_CLI_NAME})"
    )


def extract_code(
    repo_root: str | Path,
    *,
    target: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    binary = _require_bin(repo_root)
    path = str(target or repo_root)
    return _run(
        [str(binary), "extract", path, "--code-only", "--no-cluster"],
        cwd=str(repo_root),
        timeout=600,
    )


def run_query(
    question: str,
    *,
    repo_root: str | Path,
    graph: str | Path | None = None,
    budget: int = 2000,
) -> subprocess.CompletedProcess[str]:
    binary = _require_bin(repo_root)
    cmd = [str(binary), "query", question, "--budget", str(budget)]
    if graph is not None:
        cmd.extend(["--graph", str(graph)])
    return _run(cmd, cwd=str(repo_root), timeout=60)


def run_path(
    start: str,
    goal: str,
    *,
    repo_root: str | Path,
    graph: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    binary = _require_bin(repo_root)
    cmd = [str(binary), "path", start, goal]
    if graph is not None:
        cmd.extend(["--graph", str(graph)])
    return _run(cmd, cwd=str(repo_root), timeout=60)


def run_explain(
    node: str,
    *,
    repo_root: str | Path,
    graph: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    binary = _require_bin(repo_root)
    cmd = [str(binary), "explain", node]
    if graph is not None:
        cmd.extend(["--graph", str(graph)])
    return _run(cmd, cwd=str(repo_root), timeout=60)


def _require_bin(repo_root: str | Path | None) -> Path:
    binary = resolve_graphify_bin(repo_root)
    if binary is None:
        raise GraphifyCliError(
            "Official graphify CLI not found. Install with: uv tool install graphifyy"
        )
    return binary


def _run(
    argv: Sequence[str],
    *,
    cwd: str | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        list(argv),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
