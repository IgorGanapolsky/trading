#!/usr/bin/env python3
"""Maintainability signals (GitClear Maintainability Gap FORMAT steal).

GitClear/TNS: AI raised output ~25% while block duplication +81%, moved/refactor
collapsed, error-masking +47%, two-week churn +15%. This CLI measures those
signals locally — Diff Delta proxy, hotspots, tripwires — without GitClear SaaS.

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

# GitClear-style floors (directional; local proxies, not their SaaS numbers).
DEFAULT_MAX_BLOCKS_PER_MILLION = 80.0
DEFAULT_MIN_MOVED_RATIO = 0.05  # 5% of churn as renames/moves (was ~21% pre-AI)
DEFAULT_MIN_LINES = 10  # GitClear studies use ≥5; we default 10 to cut noise
DEFAULT_MAX_MASKING_PER_KLOC = 5.0
DEFAULT_MAX_CHURN_RETOUCH_RATIO = 0.35
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

# Error-masking constructs (GitClear +47% risk signal) — Python-focused.
MASKING_PATTERNS = [
    (re.compile(r"^\s*except\s*:\s*(pass\s*)?(#.*)?$"), "bare_except"),
    (
        re.compile(r"^\s*except\s+Exception(\s+as\s+\w+)?\s*:\s*pass\s*(#.*)?$"),
        "except_exception_pass",
    ),
    (
        re.compile(r"^\s*except\s+BaseException(\s+as\s+\w+)?\s*:\s*pass\s*(#.*)?$"),
        "except_base_pass",
    ),
    (re.compile(r"contextlib\.suppress\("), "contextlib_suppress"),
    (re.compile(r"^\s*except\s+.+:\s*\.\.\.\s*(#.*)?$"), "except_ellipsis"),
]


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


def scan_error_masking(files: list[Path], *, root: Path = ROOT) -> dict:
    """Count error-masking constructs (GitClear risk signal +47%)."""
    hits: list[dict] = []
    total_lines = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        total_lines += len(lines)
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        for i, line in enumerate(lines, start=1):
            for pat, kind in MASKING_PATTERNS:
                if pat.search(line):
                    hits.append(
                        {
                            "path": rel,
                            "line": i,
                            "kind": kind,
                            "preview": line.strip()[:100],
                        }
                    )
                    break
    kloc = (total_lines / 1000.0) if total_lines else 0.0
    per_kloc = (len(hits) / kloc) if kloc else 0.0
    return {
        "hits": hits[:40],
        "hit_count": len(hits),
        "physical_lines": total_lines,
        "masking_per_kloc": round(per_kloc, 3),
    }


def hotspot_directories(dup: dict, *, top_n: int = 10) -> dict:
    """Folders where duplicate blocks concentrate (GitClear AI hotspot FORMAT)."""
    by_dir: dict[str, int] = defaultdict(int)
    for group in dup.get("top_groups") or []:
        for site in group.get("sites") or []:
            path = site.get("path") or ""
            parent = str(Path(path).parent) if path else "."
            by_dir[parent] += 1
    ranked = sorted(by_dir.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    return {
        "directories": [{"path": p, "dup_site_hits": n} for p, n in ranked],
        "note": "Coach/gate directories with elevated duplication before it compounds",
    }


def two_week_churn(*, repo: Path, days: int = 14) -> dict:
    """Files retouched across consecutive windows (GitClear churn +15% proxy)."""
    git_bin = shutil.which("git")
    if not git_bin:
        return {"ok": False, "error": "git not found", "retouch_ratio": None}

    def _changed_since(since: str, until: str | None = None) -> set[str]:
        cmd = [
            git_bin,
            "-C",
            str(repo),
            "log",
            f"--since={since}",
            "--name-only",
            "--pretty=format:",
        ]
        if until:
            cmd.insert(4, f"--until={until}")
        try:
            proc = subprocess.run(  # nosec B603
                cmd, capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return set()
        out = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("commit "):
                out.add(line)
        return out

    recent = _changed_since(f"{days} days ago")
    prior = _changed_since(f"{days * 2} days ago", until=f"{days} days ago")
    retouched = recent & prior
    ratio = (len(retouched) / len(recent)) if recent else None
    return {
        "ok": True,
        "window_days": days,
        "files_changed_recent": len(recent),
        "files_changed_prior": len(prior),
        "files_retouched": len(retouched),
        "retouch_ratio": round(ratio, 4) if ratio is not None else None,
        "sample": sorted(retouched)[:15],
        "note": "High retouch ratio ≈ churn / rework (structure debt), not durable Diff Delta",
    }


def diff_delta_proxy(*, repo: Path, rev_range: str) -> dict:
    """Approximate Diff Delta: durable net change vs raw volume; renames don't inflate."""
    git_bin = shutil.which("git")
    if not git_bin:
        return {"ok": False, "error": "git not found"}
    try:
        name_status = subprocess.run(  # nosec B603
            [
                git_bin,
                "-C",
                str(repo),
                "log",
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
        numstat = subprocess.run(  # nosec B603
            [
                git_bin,
                "-C",
                str(repo),
                "log",
                "-M",
                "-C",
                "--numstat",
                "--pretty=format:",
                rev_range,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}

    renames = 0
    for line in name_status.stdout.splitlines():
        st = line.strip().split("\t", 1)[0] if line.strip() else ""
        if st.startswith("R") or st.startswith("C"):
            renames += 1

    added = deleted = 0
    for line in numstat.stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        a, d = parts[0], parts[1]
        if a.isdigit():
            added += int(a)
        if d.isdigit():
            deleted += int(d)

    volume = added + deleted
    durable_net = added - deleted
    return {
        "ok": True,
        "rev_range": rev_range,
        "lines_added": added,
        "lines_deleted": deleted,
        "raw_volume": volume,
        "durable_net": durable_net,
        "rename_or_copy_files": renames,
        "durable_share_of_volume": round(abs(durable_net) / volume, 4) if volume else None,
        "note": (
            "Diff Delta FORMAT: moves/renames keep lineage — do not treat raw LOC "
            "or PR count as AI ROI (GitClear)"
        ),
    }


def tripwires(*, breaches: list[dict], masking: dict, churn: dict | None) -> list[dict]:
    """GitClear's five concrete tripwires — local status, not a product clone."""
    dup_breach = any(b.get("metric") == "blocks_per_million" for b in breaches)
    moved_breach = any(b.get("metric") == "moved_ratio" for b in breaches)
    mask_hot = (masking.get("masking_per_kloc") or 0) > DEFAULT_MAX_MASKING_PER_KLOC
    churn_hot = bool(
        churn
        and churn.get("retouch_ratio") is not None
        and churn["retouch_ratio"] > DEFAULT_MAX_CHURN_RETOUCH_RATIO
    )
    return [
        {
            "id": 1,
            "name": "budget_refactor_and_legacy",
            "status": "warn" if moved_breach else "ok",
            "action": "Schedule extract/move + touch >12mo files; do not skip as side quest",
        },
        {
            "id": 2,
            "name": "duplicate_block_tripwire",
            "status": "fail" if dup_breach else "ok",
            "action": "Fail PR / tick when blocks_per_million exceeds floor",
        },
        {
            "id": 3,
            "name": "review_error_masking",
            "status": "warn" if mask_hot else "ok",
            "action": "Ban bare except / Exception: pass in agent-authored code",
        },
        {
            "id": 4,
            "name": "coach_thin_judgment_hotspots",
            "status": "warn" if dup_breach or mask_hot else "ok",
            "action": "Gate directories with elevated dup/masking (AI hotspot FORMAT)",
        },
        {
            "id": 5,
            "name": "measure_structure_not_volume",
            "status": "warn" if churn_hot else "ok",
            "action": "Prefer Diff Delta proxy + moved_ratio over LOC/PR velocity claims",
        },
    ]


def evaluate(
    *,
    root: Path = ROOT,
    paths: list[str] | None = None,
    min_lines: int = DEFAULT_MIN_LINES,
    max_blocks_per_million: float = DEFAULT_MAX_BLOCKS_PER_MILLION,
    git_range: str | None = None,
    min_moved_ratio: float = DEFAULT_MIN_MOVED_RATIO,
    churn_days: int | None = None,
    max_masking_per_kloc: float = DEFAULT_MAX_MASKING_PER_KLOC,
    max_churn_retouch_ratio: float = DEFAULT_MAX_CHURN_RETOUCH_RATIO,
) -> dict:
    files = _iter_py_files(root, paths)
    dup = find_duplicate_blocks(files, min_lines=min_lines, root=root)
    masking = scan_error_masking(files, root=root)
    hotspots = hotspot_directories(dup)
    moved = moved_code_ratio(repo=root, rev_range=git_range) if git_range else None
    delta = diff_delta_proxy(repo=root, rev_range=git_range) if git_range else None
    churn = two_week_churn(repo=root, days=churn_days) if churn_days else None

    breaches: list[dict] = []
    if dup["blocks_per_million"] > max_blocks_per_million:
        breaches.append(
            {
                "metric": "blocks_per_million",
                "value": dup["blocks_per_million"],
                "threshold": max_blocks_per_million,
                "why": "GitClear: block duplication +81% — keep density bounded",
            }
        )
    if moved and moved.get("moved_ratio") is not None:
        if moved["moved_ratio"] < min_moved_ratio and moved["churn_files"] >= 10:
            breaches.append(
                {
                    "metric": "moved_ratio",
                    "value": moved["moved_ratio"],
                    "threshold": min_moved_ratio,
                    "why": "GitClear: moved/refactor collapsed (21%→3.8%) — prefer extract/move",
                }
            )
    if masking["masking_per_kloc"] > max_masking_per_kloc:
        breaches.append(
            {
                "metric": "masking_per_kloc",
                "value": masking["masking_per_kloc"],
                "threshold": max_masking_per_kloc,
                "why": "GitClear: error-masking constructs +47% — surface failures, don't swallow",
            }
        )
    if (
        churn
        and churn.get("retouch_ratio") is not None
        and churn["files_changed_recent"] >= 5
        and churn["retouch_ratio"] > max_churn_retouch_ratio
    ):
        breaches.append(
            {
                "metric": "churn_retouch_ratio",
                "value": churn["retouch_ratio"],
                "threshold": max_churn_retouch_ratio,
                "why": "GitClear: two-week churn ↑ — retouches are rework, not Diff Delta",
            }
        )

    wires = tripwires(breaches=breaches, masking=masking, churn=churn)
    return {
        "ok": len(breaches) == 0,
        "framework": "dup_health",
        "stolen_format": (
            "GitClear Maintainability Gap + Diff Delta / hotspot / tripwire FORMAT "
            "(not a GitClear product clone; no vendor AI attribution)"
        ),
        "ts": datetime.now(UTC).isoformat(),
        "duplication": dup,
        "error_masking": masking,
        "hotspots": hotspots,
        "moved_code": moved,
        "diff_delta_proxy": delta,
        "churn": churn,
        "tripwires": wires,
        "thresholds": {
            "max_blocks_per_million": max_blocks_per_million,
            "min_moved_ratio": min_moved_ratio if git_range else None,
            "max_masking_per_kloc": max_masking_per_kloc,
            "max_churn_retouch_ratio": max_churn_retouch_ratio if churn_days else None,
        },
        "breaches": breaches,
        "practices": {
            "message": "Measure structure, not (just) volume — Diff Delta over LOC/PR count",
            "prefer": "extract/move + surface errors; budget legacy touch; gate hotspot dirs",
            "never": "Buy GitClear SaaS / claim AI ROI from lines authored alone",
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
        help="Optional rev range for moved/copy + Diff Delta proxy (e.g. HEAD~30..HEAD)",
    )
    p.add_argument("--min-moved-ratio", type=float, default=DEFAULT_MIN_MOVED_RATIO)
    p.add_argument(
        "--churn-days",
        type=int,
        default=None,
        help="Enable two-window retouch churn (e.g. 14)",
    )
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = evaluate(
        paths=args.path or None,
        min_lines=args.min_lines,
        max_blocks_per_million=args.max_blocks_per_million,
        git_range=args.git_range,
        min_moved_ratio=args.min_moved_ratio,
        churn_days=args.churn_days,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
