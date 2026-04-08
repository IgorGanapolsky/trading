"""Helpers for resolving shared git paths across primary checkouts and worktrees."""

from __future__ import annotations

from pathlib import Path


def resolve_shared_repo_root(anchor: Path) -> Path:
    """Return the shared repo root for a checkout or git worktree."""
    anchor = anchor.resolve()
    for candidate in (anchor, *anchor.parents):
        git_marker = candidate / ".git"
        if git_marker.is_dir():
            return candidate
        if not git_marker.is_file():
            continue
        try:
            first_line = git_marker.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, IndexError):
            return candidate
        prefix = "gitdir: "
        if not first_line.startswith(prefix):
            return candidate
        git_dir = Path(first_line[len(prefix) :])
        if not git_dir.is_absolute():
            git_dir = (candidate / git_dir).resolve()
        if git_dir.parent.name == "worktrees":
            return git_dir.parent.parent.parent
        if git_dir.name == ".git":
            return git_dir.parent
        return candidate
    return anchor
