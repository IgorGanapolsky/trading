#!/usr/bin/env python3
"""
Blog post linter for GH Pages / Dev.to / LinkedIn publishing.

Checks for:
- Clickbait / sensational titles
- Excessive punctuation or ALL CAPS
- Missing title/description/hero image in front matter
- Very short content
- max-image-preview:large meta tag presence

Usage:
  python3 scripts/lint_blog_posts.py --changed --strict
  python3 scripts/lint_blog_posts.py --all
  python3 scripts/lint_blog_posts.py --paths docs/_posts/foo.md
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DIRS = [
    REPO_ROOT / "docs" / "_posts",
    REPO_ROOT / "docs" / "_reports",
    REPO_ROOT / "docs" / "_discoveries",
]

META_FILES = [
    REPO_ROOT / "docs" / "_includes" / "head-custom.html",
    REPO_ROOT / "docs" / "_layouts" / "default.html",
]

CLICKBAIT_PATTERNS = [
    re.compile(r"\byou won't believe\b", re.IGNORECASE),
    re.compile(r"\bshocking\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bthis one trick\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\b", re.IGNORECASE),
    re.compile(r"\bfree money\b", re.IGNORECASE),
    re.compile(r"\binstant(ly)?\b", re.IGNORECASE),
    re.compile(r"\bexplode(s|d)?\b", re.IGNORECASE),
    re.compile(r"\bskyrocket(s|ed)?\b", re.IGNORECASE),
]

SENSATIONAL_PATTERNS = [
    re.compile(r"[!?]{2,}"),  # !!, ??, !?
    re.compile(r"\bAMAZING\b"),
    re.compile(r"\bINSANE\b"),
    re.compile(r"\bCRAZY\b"),
]

IMAGE_KEYS = {"image", "image_url", "image_path", "cover_image", "hero_image"}
DESC_KEYS = {"description", "summary", "excerpt"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return {}, text
    raw = parts[0].strip("-\n")
    body = parts[1].lstrip("\n")
    meta = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    return meta, body


def _extract_title(meta: dict, body: str, fallback: str) -> str:
    if "title" in meta and meta["title"]:
        return meta["title"]
    match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def _has_required_meta() -> bool:
    for meta_file in META_FILES:
        if not meta_file.exists():
            continue
        content = _read_text(meta_file)
        if "max-image-preview:large" in content:
            return True
    return False


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def lint_file(path: Path) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    text = _read_text(path)
    meta, body = _parse_frontmatter(text)
    title = _extract_title(meta, body, path.name)

    if not title:
        issues.append(("error", "missing title"))

    if title:
        if len(title) > 90:
            issues.append(("error", f"title too long ({len(title)} chars)"))
        elif len(title) > 70:
            issues.append(("warn", f"title long ({len(title)} chars)"))

        for pattern in CLICKBAIT_PATTERNS:
            if pattern.search(title):
                issues.append(("error", f"clickbait pattern: '{pattern.pattern}'"))
                break

        for pattern in SENSATIONAL_PATTERNS:
            if pattern.search(title):
                issues.append(("warn", "sensational punctuation or ALL CAPS"))
                break

        if re.search(r"\b[A-Z]{4,}\b", title):
            issues.append(("warn", "ALL CAPS word in title"))

    if not any(key in meta and meta[key] for key in DESC_KEYS):
        issues.append(("warn", "missing description/summary in front matter"))

    if not any(key in meta and meta[key] for key in IMAGE_KEYS):
        issues.append(("warn", "missing hero image in front matter"))

    if _word_count(body) < 200:
        issues.append(("warn", "content very short (<200 words)"))

    return issues


def _collect_changed_files() -> list[Path]:
    candidates: list[str] = []
    cmds = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR"],
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "--cached"],
    ]
    for cmd in cmds:
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            candidates.extend(result.stdout.splitlines())
        except Exception:
            continue

    # If running in CI for PRs, use base ref diff
    base_ref = (os.environ.get("GITHUB_BASE_REF") or "").strip()
    if base_ref:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
            candidates.extend(result.stdout.splitlines())
        except Exception:
            pass

    # Deduplicate
    unique = []
    seen = set()
    for item in candidates:
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)

    return [Path(p) for p in unique]


def _collect_all_files() -> list[Path]:
    files: list[Path] = []
    for directory in DEFAULT_DIRS:
        if directory.exists():
            files.extend(directory.rglob("*.md"))
    return files


def _filter_posts(paths: list[Path]) -> list[Path]:
    allowed = []
    for path in paths:
        if path.suffix.lower() != ".md":
            continue
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = None
        if rel is not None:
            parts = rel.parts
            if len(parts) >= 2 and parts[0] == "docs" and parts[1].startswith("_"):
                allowed.append(path if path.is_absolute() else REPO_ROOT / path)
                continue
        # Absolute path fallback: look for /docs/_* in the path
        parts = path.parts
        for i, part in enumerate(parts):
            if part == "docs" and i + 1 < len(parts) and parts[i + 1].startswith("_"):
                allowed.append(path if path.is_absolute() else REPO_ROOT / path)
                break
    return allowed


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint blog posts")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--changed", action="store_true", help="Lint changed files only")
    group.add_argument("--all", action="store_true", help="Lint all blog posts")
    group.add_argument("--paths", nargs="+", help="Explicit file paths to lint")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings")
    parser.add_argument("--warn-only", action="store_true", help="Never fail")
    args = parser.parse_args()

    if not _has_required_meta():
        print("ERROR: missing max-image-preview:large meta tag in head include/layout")
        if not args.warn_only:
            return 2

    if args.paths:
        files = [Path(p) for p in args.paths]
    elif args.changed:
        files = _collect_changed_files()
    else:
        files = _collect_all_files()

    files = _filter_posts(files)

    if not files:
        print("No blog posts to lint.")
        return 0

    total_issues = 0
    total_errors = 0
    total_warnings = 0

    for path in sorted(set(files)):
        path = path if path.is_absolute() else REPO_ROOT / path
        issues = lint_file(path)
        if not issues:
            continue
        rel = path.relative_to(REPO_ROOT)
        print(f"\n{rel}")
        for level, message in issues:
            total_issues += 1
            if level == "error":
                total_errors += 1
            else:
                total_warnings += 1
            print(f"  [{level.upper()}] {message}")

    print("\nSummary:")
    print(f"  Files checked: {len(files)}")
    print(f"  Errors: {total_errors}")
    print(f"  Warnings: {total_warnings}")

    if args.warn_only:
        return 0
    if args.strict and (total_errors or total_warnings):
        return 2
    if total_errors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
