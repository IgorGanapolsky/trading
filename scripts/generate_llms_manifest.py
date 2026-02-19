#!/usr/bin/env python3
"""
Generate markdown manifests for AI crawler discoverability.

Outputs:
- docs/llms.txt
- docs/llms-full.txt
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

SITE_NAME = "AI Trading Journey"
SITE_URL = "https://igorganapolsky.github.io/trading"
REPO_URL = "https://github.com/IgorGanapolsky/trading"

POSTS_SUBDIR = "docs/_posts"
REPORTS_SUBDIR = "docs/_reports"
LESSONS_SUBDIR = "rag_knowledge/lessons_learned"
WORKFLOWS_SUBDIR = ".github/workflows"

LLMS_PATH = "docs/llms.txt"
LLMS_FULL_PATH = "docs/llms-full.txt"

FRONT_MATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
TITLE_PATTERN = re.compile(r"^title:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
H1_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
POST_NAME_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>.+)$")
LESSON_DATE_PATTERN = re.compile(r"^\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)

MAX_RECENT_POSTS = 12
MAX_LISTED_POSTS = 100
MAX_LISTED_LESSONS = 120


@dataclass(frozen=True)
class ContentEntry:
    title: str
    url: str
    date: str | None
    source: Path


def _clean_title(raw: str) -> str:
    return raw.strip().strip('"').strip("'").strip()


def _humanize_name(stem: str) -> str:
    words = stem.replace("-", " ").replace("_", " ").split()
    if not words:
        return stem
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


def _extract_title(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return _humanize_name(path.stem)

    front_matter_match = FRONT_MATTER_PATTERN.match(text)
    if front_matter_match:
        title_match = TITLE_PATTERN.search(front_matter_match.group(1))
        if title_match:
            return _clean_title(title_match.group(1))

    h1_match = H1_PATTERN.search(text)
    if h1_match:
        return _clean_title(h1_match.group(1))

    return _humanize_name(path.stem)


def _extract_lesson_date(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = LESSON_DATE_PATTERN.search(text)
    return match.group(1) if match else None


def _collect_posts(posts_dir: Path, site_url: str) -> list[ContentEntry]:
    entries: list[ContentEntry] = []
    for path in sorted(posts_dir.glob("*.md")):
        match = POST_NAME_PATTERN.match(path.stem)
        if not match:
            continue
        date = match.group("date")
        slug = match.group("slug")
        year, month, day = date.split("-")
        entries.append(
            ContentEntry(
                title=_extract_title(path),
                url=f"{site_url}/{year}/{month}/{day}/{slug}.html",
                date=date,
                source=path,
            )
        )
    entries.sort(key=lambda entry: ((entry.date or ""), entry.source.name), reverse=True)
    return entries


def _collect_reports(reports_dir: Path, site_url: str) -> list[ContentEntry]:
    entries: list[ContentEntry] = []
    for path in sorted(reports_dir.glob("*.md")):
        date = None
        match = POST_NAME_PATTERN.match(path.stem)
        if match:
            date = match.group("date")
        entries.append(
            ContentEntry(
                title=_extract_title(path),
                url=f"{site_url}/reports/{path.stem}/",
                date=date,
                source=path,
            )
        )
    entries.sort(key=lambda entry: ((entry.date or ""), entry.source.name), reverse=True)
    return entries


def _collect_lessons(lessons_dir: Path, repo_url: str, root: Path) -> list[ContentEntry]:
    entries: list[ContentEntry] = []
    for path in sorted(lessons_dir.glob("*.md")):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.name
        entries.append(
            ContentEntry(
                title=_extract_title(path),
                url=f"{repo_url}/blob/main/{relative}",
                date=_extract_lesson_date(path),
                source=path,
            )
        )
    entries.sort(key=lambda entry: ((entry.date or ""), entry.source.name), reverse=True)
    return entries


def _count_workflows(workflows_dir: Path) -> int:
    yaml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    return len(yaml_files)


def _render_llms_summary(
    posts: list[ContentEntry],
    reports: list[ContentEntry],
    lessons: list[ContentEntry],
    workflow_count: int,
    site_url: str,
    repo_url: str,
) -> str:
    latest_post_date = posts[0].date if posts else "unknown"
    latest_lesson_date = next((entry.date for entry in lessons if entry.date), "unknown")

    lines = [
        f"# {SITE_NAME} - LLM Index",
        "> Autonomous AI trading system built in public.",
        "",
        "## North Star",
        "- Target: $6,000/month after-tax (ASAP; no fixed date).",
        "- Path: SPY iron condor system with strict risk gates and continuous learning.",
        "",
        "## Canonical URLs",
        f"- Home: {site_url}/",
        f"- Blog RSS feed: {site_url}/feed.xml",
        f"- Reports: {site_url}/reports/",
        f"- Lessons index: {site_url}/lessons/",
        f"- RAG query UI: {site_url}/rag-query/",
        f"- Repository: {repo_url}",
        f"- Full markdown catalog: {site_url}/llms-full.txt",
        "",
        "## Content Snapshot",
        f"- Blog posts published: {len(posts)}",
        f"- Reports published: {len(reports)}",
        f"- Lessons in RAG markdown: {len(lessons)}",
        f"- Automation workflows: {workflow_count}",
        f"- Latest blog post date: {latest_post_date}",
        f"- Latest lesson date: {latest_lesson_date}",
        "",
        "## Tech Stack (How It Plays Together)",
        "- Market + execution: Alpaca APIs (paper/live).",
        "- Decision layer: Claude Opus for trade-critical reasoning; routed non-critical workloads via TARS/OpenRouter.",
        "- Memory layer: LanceDB-backed RAG over lessons and failure history.",
        "- Orchestration layer: Python orchestrator + rule gates for SPY-only, sizing, and exits.",
        "- Reliability layer: GitHub Actions + Ralph Mode self-healing loops.",
        "",
        "## Recent Posts",
    ]

    for entry in posts[:MAX_RECENT_POSTS]:
        date_text = entry.date or "unknown-date"
        lines.append(f"- [{entry.title}]({entry.url}) - {date_text}")

    lines.extend(
        [
            "",
            "## Machine-Readable Policy",
            "- This file is auto-generated; do not edit manually.",
            "- Generator: `scripts/generate_llms_manifest.py`.",
            "- Automation: `.github/workflows/refresh-llms-manifests.yml`.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_llms_full(
    posts: list[ContentEntry],
    reports: list[ContentEntry],
    lessons: list[ContentEntry],
    workflow_count: int,
    site_url: str,
    repo_url: str,
) -> str:
    lines = [
        f"# {SITE_NAME} - Full LLM Catalog",
        "> Full markdown index for AI retrieval and content agents.",
        "",
        "## Discovery Endpoints",
        f"- LLM summary: {site_url}/llms.txt",
        f"- LLM full: {site_url}/llms-full.txt",
        f"- Sitemap: {site_url}/sitemap.xml",
        f"- RSS: {site_url}/feed.xml",
        "",
        "## Repository Discoverability",
        f"- Repo root: {repo_url}",
        f"- Source code: {repo_url}/tree/main/src",
        f"- Workflows: {repo_url}/tree/main/.github/workflows",
        f"- Scripts: {repo_url}/tree/main/scripts",
        "",
        "## Operational Metrics",
        f"- Workflows configured: {workflow_count}",
        f"- Blog posts indexed: {len(posts)}",
        f"- Reports indexed: {len(reports)}",
        f"- Lessons indexed: {len(lessons)}",
        "",
        "## Blog Posts (Newest First)",
    ]

    for entry in posts[:MAX_LISTED_POSTS]:
        date_text = entry.date or "unknown-date"
        lines.append(f"- [{entry.title}]({entry.url}) - {date_text}")

    lines.append("")
    lines.append("## Reports")
    if reports:
        for entry in reports:
            date_text = entry.date or "undated"
            lines.append(f"- [{entry.title}]({entry.url}) - {date_text}")
    else:
        lines.append("- No reports found.")

    lines.append("")
    lines.append("## Lessons (Source Markdown)")
    for entry in lessons[:MAX_LISTED_LESSONS]:
        date_text = entry.date or "undated"
        lines.append(f"- [{entry.title}]({entry.url}) - {date_text}")

    lines.extend(
        [
            "",
            "## Notes",
            "- Lesson links point to source markdown in GitHub.",
            "- This file is auto-generated by `scripts/generate_llms_manifest.py`.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_manifests(
    root: Path,
    site_url: str = SITE_URL,
    repo_url: str = REPO_URL,
) -> tuple[str, str]:
    posts = _collect_posts(root / POSTS_SUBDIR, site_url=site_url)
    reports = _collect_reports(root / REPORTS_SUBDIR, site_url=site_url)
    lessons = _collect_lessons(root / LESSONS_SUBDIR, repo_url=repo_url, root=root)
    workflow_count = _count_workflows(root / WORKFLOWS_SUBDIR)

    return (
        _render_llms_summary(
            posts=posts,
            reports=reports,
            lessons=lessons,
            workflow_count=workflow_count,
            site_url=site_url,
            repo_url=repo_url,
        ),
        _render_llms_full(
            posts=posts,
            reports=reports,
            lessons=lessons,
            workflow_count=workflow_count,
            site_url=site_url,
            repo_url=repo_url,
        ),
    )


def _write_if_changed(path: Path, content: str, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == content:
        return False
    if check:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/llms.txt and docs/llms-full.txt.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--check", action="store_true", help="Exit non-zero if files are stale.")
    args = parser.parse_args()

    root = args.root.resolve()
    summary, full = generate_manifests(root=root)
    summary_path = root / LLMS_PATH
    full_path = root / LLMS_FULL_PATH

    summary_changed = _write_if_changed(summary_path, summary, check=args.check)
    full_changed = _write_if_changed(full_path, full, check=args.check)

    if args.check:
        if summary_changed or full_changed:
            print("llms manifests are stale. Run: python3 scripts/generate_llms_manifest.py")
            return 1
        print("llms manifests are up to date.")
        return 0

    if summary_changed:
        print(f"Updated {summary_path}")
    if full_changed:
        print(f"Updated {full_path}")
    if not summary_changed and not full_changed:
        print("No llms manifest changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
