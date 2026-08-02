#!/usr/bin/env python3
"""Scan every candidate tracked file for repository and RAG hygiene problems."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

FORBIDDEN_PREFIXES = (
    ".claude/logs/",
    "artifacts/",
    "coverage/",
    "data/agent_context/",
    "data/audit/",
    "data/backtests/",
    "data/cache/",
    "data/reports/",
    "data/screenshots/",
    "docs/assets/snapshots/",
    "logs/",
    "node_modules/",
    "reports/",
)
FORBIDDEN_NAMES = {".coverage", ".DS_Store", "coverage.json", "coverage.xml", "pytest.ini"}
BINARY_SUFFIXES = {
    ".avif",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".db",
    ".pkl",
    ".pt",
    ".webp",
    ".zip",
}
LESSON_ID_PATTERNS = (
    re.compile(r"(?im)^\s*id\s*:\s*['\"]?(LL[-_ ]?\d+)", re.IGNORECASE),
    re.compile(r"(?im)^\s*\*\*ID\*\*\s*:\s*(LL[-_ ]?\d+)", re.IGNORECASE),
    re.compile(r"(?im)^#\s+.*?\b(LL[-_ ]?\d+)\b", re.IGNORECASE),
)
FILENAME_LESSON_ID = re.compile(r"(?i)(?:^|[/_-])LL[-_ ]?(\d+)")
LOCAL_PATH_PATTERN = re.compile(r"/Users/(?!\.\.\.)[A-Za-z0-9._-]+/")
STALE_STATUS_PATTERN = re.compile(
    r"(?im)^\s*(?:\*\*)?status(?:\*\*)?\s*:\s*(IN_PROGRESS|ACTIVE CRISIS|PENDING)\b"
)


@dataclass(frozen=True)
class Finding:
    severity: str
    kind: str
    path: str
    detail: str


def _git_paths(repo: Path, *args: str) -> set[str]:
    completed = subprocess.run(["git", *args, "-z"], cwd=repo, check=True, capture_output=True)
    return {item.decode() for item in completed.stdout.split(b"\0") if item}


def candidate_paths(repo: Path) -> list[str]:
    cached = _git_paths(repo, "ls-files")
    untracked = _git_paths(repo, "ls-files", "--others", "--exclude-standard")
    return sorted(path for path in cached | untracked if (repo / path).is_file())


def physical_line_count(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def normalize_lesson_id(raw: str) -> str:
    digits = re.search(r"\d+", raw)
    return f"LL-{int(digits.group())}" if digits else raw.upper().replace("_", "-")


def lesson_id(path: str, text: str) -> str | None:
    for pattern in LESSON_ID_PATTERNS:
        if match := pattern.search(text[:3000]):
            return normalize_lesson_id(match.group(1))
    if match := FILENAME_LESSON_ID.search(path):
        return f"LL-{int(match.group(1))}"
    return None


def scan(repo: Path) -> dict:
    paths = candidate_paths(repo)
    findings: list[Finding] = []
    suffix_counts: Counter[str] = Counter()
    content_hashes: dict[str, list[str]] = defaultdict(list)
    lesson_ids: dict[str, list[str]] = defaultdict(list)
    total_lines = text_files = binary_files = 0

    for relative in paths:
        path = repo / relative
        data = path.read_bytes()
        total_lines += physical_line_count(data)
        suffix_counts[path.suffix.lower() or "[no suffix]"] += 1
        if any(relative.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            findings.append(
                Finding("error", "generated-path", relative, "tracked generated output")
            )
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in {".pyc", ".log"}:
            findings.append(
                Finding("error", "generated-file", relative, "tracked runtime artifact")
            )
        if data:
            content_hashes[hashlib.sha256(data).hexdigest()].append(relative)
        is_binary = b"\0" in data[:8192] or path.suffix.lower() in BINARY_SUFFIXES
        if is_binary:
            binary_files += 1
            continue
        text_files += 1
        text = data.decode("utf-8", errors="replace")
        if LOCAL_PATH_PATTERN.search(text) and not relative.startswith("tests/"):
            findings.append(
                Finding(
                    "error",
                    "absolute-user-path",
                    relative,
                    "contains a machine-specific /Users path",
                )
            )
        if relative.startswith("rag_knowledge/lessons_learned/"):
            if identifier := lesson_id(relative, text):
                lesson_ids[identifier].append(relative)
            else:
                findings.append(Finding("warning", "lesson-id", relative, "no lesson ID found"))
            if match := STALE_STATUS_PATTERN.search(text[:3000]):
                findings.append(
                    Finding(
                        "warning", "stale-lesson-status", relative, f"status is {match.group(1)}"
                    )
                )

    for identifier, lesson_paths in sorted(lesson_ids.items()):
        if len(lesson_paths) > 1:
            findings.append(
                Finding(
                    "error",
                    "duplicate-lesson-id",
                    ", ".join(lesson_paths),
                    f"{identifier} appears {len(lesson_paths)} times",
                )
            )

    duplicate_groups = [items for items in content_hashes.values() if len(items) > 1]
    return {
        "files_scanned": len(paths),
        "physical_lines": total_lines,
        "text_files": text_files,
        "binary_files": binary_files,
        "lesson_files": sum(len(items) for items in lesson_ids.values()),
        "duplicate_content_groups": len(duplicate_groups),
        "errors": sum(item.severity == "error" for item in findings),
        "warnings": sum(item.severity == "warning" for item in findings),
        "suffix_counts": dict(sorted(suffix_counts.items(), key=lambda item: (-item[1], item[0]))),
        "findings": [asdict(item) for item in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = scan(args.repo_root.resolve())
    payload = json.dumps(report, indent=2)
    print(payload)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
