#!/usr/bin/env python3
"""Duplication / refactor health (TNS + GitClear Maintainability Gap FORMAT).

AI coding raised output ~25% while block duplication rose ~81% and "moved code"
(refactor signature) collapsed. This CLI measures local maintainability signals
without installing GitClear.

EXIT 0 when ok (or report-only). EXIT 2 with --strict when thresholds breach.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # nosec B404
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# GitClear-style floor: flag when duplicate block density is high.
DEFAULT_MAX_BLOCKS_PER_MILLION = 80.0
DEFAULT_MIN_MOVED_RATIO = 0.05  # 5% of churn as renames/moves (was ~21% pre-AI)
DEFAULT_MIN_LINES = 10
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".trunk",
    "data",
    "models",
}


def _normalize_line(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
        return None
    # Drop inline comment tails for fuzzy match (keep strings intact-ish)
    if "#" in s and not s.strip().startswith("#"):
        in_str = False
        out = []
        for i, ch in enumerate(s):
            if ch in "\"'" and (i == 0 or s[i - 1] != "\\"):
                in_str = not in_str
            if ch == "#" and not in_str:
                s = "".join(out).rstrip()
                break
            out.append(ch)
    return re.sub(r"\s+", " ", s)


def _iter_py_files(root: Path, paths: list[str] | None) -> list[Path]:
    if paths:
        out = []
        for p in paths:
            path = (root / p).resolve() if not Path(p).is_absolute() else Path(p)
            if path.is_file() and path.suffix == ".py":
                out.append(path)
            elif path.is_dir():
                out.extend(_iter_py_files(path, None))
        return sorted(out)
    files = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def find_duplicate_blocks(
    files: list[Path],
    *,
    min_lines: int = DEFAULT_MIN_LINES,
    root: Path = ROOT,
) -> dict:
    """Hash sliding windows of normalized lines; report multi-file / multi-site dups."""
    index: dict[str, list[dict]] = defaultdict(list)
    total_lines = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        raw = text.splitlines()
        total_lines += len(raw)
        norms: list[tuple[int, str]] = []
        for i, line in enumerate(raw, start=1):
            n = _normalize_line(line)
            if n is not None:
                norms.append((i, n))
        if len(norms) < min_lines:
            continue
        for start in range(0, len(norms) - min_lines + 1):
            window = norms[start : start + min_lines]
            payload = "\n".join(w[1] for w in window)
            digest = hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()[:16]
            rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            index[digest].append(
                {
                    "path": rel,
                    "start_line": window[0][0],
                    "end_line": window[-1][0],
                    "preview": window[0][1][:80],
                }
            )

    # Collapse overlapping hits in the same file for the same digest
    groups = []
    for digest, sites in index.items():
        if len(sites) < 2:
            continue
        # Distinct (path, start) only
        uniq = []
        seen = set()
        for s in sites:
            key = (s["path"], s["start_line"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(s)
        if len(uniq) < 2:
            continue
        # Prefer cross-file or distant same-file
        paths = {u["path"] for u in uniq}
        groups.append(
            {
                "hash": digest,
                "sites": uniq[:8],
                "site_count": len(uniq),
                "cross_file": len(paths) > 1,
                "preview": uniq[0]["preview"],
            }
        )

    groups.sort(key=lambda g: (-g["site_count"], -int(g["cross_file"]), g["hash"]))
    blocks = len(groups)
    per_million = (blocks / total_lines * 1_000_000) if total_lines else 0.0
    return {
        "files_scanned": len(files),
        "physical_lines": total_lines,
        "min_lines": min_lines,
        "duplicate_block_groups": blocks,
        "blocks_per_million": round(per_million, 2),
        "top_groups": groups[:15],
    }


def moved_code_ratio(*, repo: Path, rev_range: str) -> dict:
    """Approximate GitClear 'moved code' via rename/copy detection in a git range."""
    # numstat with renames: lines look like R100\told\tnew or plain added/deleted
    git_bin = shutil.which("git")
    if not git_bin:
        return {"ok": False, "error": "git not found", "moved_ratio": None}
    try:
        proc = subprocess.run(  # nosec B603
            [
                git_bin,
                "-C",
                str(repo),
                "log",
                "--diff-filter=AMDR",
                "-M",
                "-C",
                "--name-status",
                "--pretty=format:",
                rev_range,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc), "moved_ratio": None}

    moved = 0
    churn_files = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        status = line.split("\t", 1)[0]
        churn_files += 1
        if status.startswith("R") or status.startswith("C"):
            moved += 1

    ratio = (moved / churn_files) if churn_files else None
    return {
        "ok": True,
        "rev_range": rev_range,
        "churn_files": churn_files,
        "moved_or_copied_files": moved,
        "moved_ratio": round(ratio, 4) if ratio is not None else None,
        "note": (
            "File-level rename/copy ratio (proxy for GitClear moved-code %). "
            "Pre-AI industry ~0.21 of changed lines; 2026 ~0.038."
        ),
    }


def evaluate(
    *,
    root: Path = ROOT,
    paths: list[str] | None = None,
    min_lines: int = DEFAULT_MIN_LINES,
    max_blocks_per_million: float = DEFAULT_MAX_BLOCKS_PER_MILLION,
    git_range: str | None = None,
    min_moved_ratio: float = DEFAULT_MIN_MOVED_RATIO,
) -> dict:
    files = _iter_py_files(root, paths)
    dup = find_duplicate_blocks(files, min_lines=min_lines, root=root)
    moved = moved_code_ratio(repo=root, rev_range=git_range) if git_range else None

    breaches: list[dict] = []
    if dup["blocks_per_million"] > max_blocks_per_million:
        breaches.append(
            {
                "metric": "blocks_per_million",
                "value": dup["blocks_per_million"],
                "threshold": max_blocks_per_million,
                "why": "TNS/GitClear: AI era saw +81% block duplication — keep density bounded",
            }
        )
    if moved and moved.get("moved_ratio") is not None:
        if moved["moved_ratio"] < min_moved_ratio and moved["churn_files"] >= 10:
            breaches.append(
                {
                    "metric": "moved_ratio",
                    "value": moved["moved_ratio"],
                    "threshold": min_moved_ratio,
                    "why": (
                        "TNS: moved/refactor share collapsed (21%→3.8%). "
                        "Prefer extract/move over copy-paste."
                    ),
                }
            )

    return {
        "ok": len(breaches) == 0,
        "framework": "dup_health",
        "stolen_format": (
            "TNS/GitClear Maintainability Gap — duplication↑ + moved-code↓ "
            "(not a GitClear product clone)"
        ),
        "ts": datetime.now(UTC).isoformat(),
        "duplication": dup,
        "moved_code": moved,
        "thresholds": {
            "max_blocks_per_million": max_blocks_per_million,
            "min_moved_ratio": min_moved_ratio if git_range else None,
        },
        "breaches": breaches,
        "practices": {
            "message": "Tests + refactoring are the mission, not a side quest (TNS)",
            "prefer": "extract/move shared helpers over copy-paste under AI velocity pressure",
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", action="append", default=[], help="Limit scan (repeatable)")
    p.add_argument("--min-lines", type=int, default=DEFAULT_MIN_LINES)
    p.add_argument(
        "--max-blocks-per-million",
        type=float,
        default=DEFAULT_MAX_BLOCKS_PER_MILLION,
    )
    p.add_argument(
        "--git-range",
        default=None,
        help="Optional rev range for moved/copy ratio (e.g. HEAD~30..HEAD)",
    )
    p.add_argument("--min-moved-ratio", type=float, default=DEFAULT_MIN_MOVED_RATIO)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = evaluate(
        paths=args.path or None,
        min_lines=args.min_lines,
        max_blocks_per_million=args.max_blocks_per_million,
        git_range=args.git_range,
        min_moved_ratio=args.min_moved_ratio,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
