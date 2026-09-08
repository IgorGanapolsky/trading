#!/usr/bin/env python3
"""Fail if staged (or listed) non-test files contain machine-specific /Users paths.

Cheap local gate so absolute-user-path hygiene fails before push, not only in CI.
Uses the same pattern as scripts/audit_repository_hygiene.py.

Default mode reads blob contents from the Git index (`git show :path`) so a
staged absolute path cannot be hidden by cleaning the working tree afterward.
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

from scripts.audit_repository_hygiene import LOCAL_PATH_PATTERN


def _staged_paths(repo: Path) -> list[str]:
    completed = subprocess.run(  # nosec B603 B607
        ["git", "diff", "--cached", "--name-only", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return [item.decode() for item in completed.stdout.split(b"\0") if item]


def _read_index_text(repo: Path, relative: str) -> str | None:
    completed = subprocess.run(  # nosec B603 B607
        ["git", "show", f":{relative}"],
        cwd=repo,
        capture_output=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.decode("utf-8", errors="replace")


def check_paths(
    repo: Path,
    paths: list[str],
    *,
    from_index: bool = False,
) -> list[str]:
    bad: list[str] = []
    for relative in paths:
        if relative.startswith("tests/"):
            continue
        if from_index:
            text = _read_index_text(repo, relative)
            if text is None:
                continue
        else:
            path = repo / relative
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        if LOCAL_PATH_PATTERN.search(text):
            bad.append(relative)
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional paths to scan from the filesystem; default = git staged index blobs",
    )
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()
    explicit = bool(args.paths)
    paths = list(args.paths) if explicit else _staged_paths(repo)
    bad = check_paths(repo, paths, from_index=not explicit)
    if bad:
        print("absolute-user-path: machine-specific /Users path in:", file=sys.stderr)
        for item in bad:
            print(f"  {item}", file=sys.stderr)
        print("Scrub to /Users/.../ before commit (see LL-588).", file=sys.stderr)
        return 1
    print(f"ok: scanned {len(paths)} path(s), no absolute-user-path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
