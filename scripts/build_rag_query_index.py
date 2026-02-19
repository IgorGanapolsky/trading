#!/usr/bin/env python3
"""Build a compact JSON index for the RAG query UI and worker.

Reads rag_knowledge/**/*.md and emits data/rag/lessons_query.json.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

RAG_ROOT = Path("rag_knowledge")
OUTPUT_PATHS = [
    Path("data/rag/lessons_query.json"),
    Path("docs/data/rag/lessons_query.json"),
]
LESSONS_PAGE_PATH = Path("docs/lessons/index.html")

DATE_PATTERNS = [
    re.compile(r"\*\*Date(?:\*\*:|:\*\*)\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\bDate\b:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE),
]
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
TRUTHY = {"1", "true", "yes", "on"}
MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _extract_field(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _extract_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple YAML frontmatter key/value pairs from markdown text."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    parsed: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip().lower()] = value.strip().strip('"').strip("'")
    return parsed


def _extract_tags(text: str) -> list[str]:
    if "## Tags" in text:
        tags_section = text.split("## Tags", 1)[1]
        return re.findall(r"`([^`]+)`", tags_section)
    return []


def _extract_summary(text: str) -> str:
    summary = _extract_field(
        re.compile(r"^##\s+Summary\s*\n(.*?)(?=\n##|\Z)", re.DOTALL | re.MULTILINE),
        text,
    )
    if summary:
        return " ".join(summary.strip().split())

    # Remove title and metadata lines
    lines = []
    for line in text.splitlines():
        if line.startswith("# "):
            continue
        if line.strip().startswith("**") and "**:" in line:
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:400]


def _parse_date_value(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        # Support ISO timestamps from frontmatter dates like 2026-02-16T13:46:26Z
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _has_explicit_time(raw: str) -> bool:
    return bool(re.search(r"(?:T|\s)\d{1,2}:\d{2}", raw))


def _to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _infer_date_from_path(path: Path) -> datetime | None:
    stem = path.stem.lower()

    ymd_compact = re.search(r"(20\d{2})(\d{2})(\d{2})", stem)
    if ymd_compact:
        year, month, day = map(int, ymd_compact.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            pass

    ymd_dashed = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", stem)
    if ymd_dashed:
        year, month, day = map(int, ymd_dashed.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            pass

    month_day = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{1,2})(?!\d)", stem)
    if month_day:
        month_txt, day_txt = month_day.groups()
        day = int(day_txt)
        month = MONTH_MAP[month_txt]
        year_match = re.search(r"(20\d{2})", stem)
        year = int(year_match.group(1)) if year_match else datetime.now(timezone.utc).year
        try:
            return datetime(year, month, day)
        except ValueError:
            pass

    return None


def _parse_date(
    text: str, frontmatter_date: str = "", path: Path | None = None
) -> tuple[str, datetime | None]:
    fallback_raw = frontmatter_date or ""
    if frontmatter_date:
        parsed = _parse_date_value(frontmatter_date)
        if parsed:
            return frontmatter_date, parsed

    for pattern in DATE_PATTERNS:
        raw = _extract_field(pattern, text)
        if raw:
            parsed = _parse_date_value(raw)
            if parsed:
                return raw, parsed
            if not fallback_raw:
                fallback_raw = raw

    if path is not None:
        inferred = _infer_date_from_path(path)
        if inferred:
            return inferred.strftime("%Y-%m-%d"), inferred

    return fallback_raw, None


def _is_noise_artifact_lesson(
    path: Path, title: str, frontmatter: dict[str, str], text: str
) -> bool:
    source = (frontmatter.get("source") or "").lower()
    stem = path.stem.lower()
    title_norm = title.lower()

    if source == "tars_artifact_ingest":
        return True
    if stem.startswith("tars_"):
        return True
    if title_norm.startswith("tars artifact ingest"):
        return True
    return "Normalized TARS artifact ingested for RAG retrieval." in text


def build_index() -> list[dict]:
    lessons = []
    if not RAG_ROOT.exists():
        return lessons
    indexed_at_utc = _to_utc_iso(datetime.now(timezone.utc))
    include_artifact_ingest = (
        os.getenv("INCLUDE_ARTIFACT_INGEST_LESSONS", "").strip().lower() in TRUTHY
    )

    for path in sorted(RAG_ROOT.rglob("*.md")):
        if path.stem.startswith("tars_") and not include_artifact_ingest:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter = _parse_frontmatter(text)
        rel_path = path.relative_to(RAG_ROOT)
        category = rel_path.parts[0] if rel_path.parts else "general"
        source_path = f"rag_knowledge/{rel_path.as_posix()}"
        source_mtime_utc = _to_utc_iso(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))

        if category == "lessons_learned":
            item_id = path.stem
        else:
            item_id = rel_path.with_suffix("").as_posix()

        title = frontmatter.get("title") or _extract_title(text, item_id)
        if not include_artifact_ingest and _is_noise_artifact_lesson(
            path, title, frontmatter, text
        ):
            continue

        date_raw, date_obj = _parse_date(text, frontmatter.get("date", ""), path=path)
        event_timestamp_utc = ""
        if date_obj and date_raw and _has_explicit_time(date_raw):
            event_timestamp_utc = _to_utc_iso(date_obj)
        else:
            # Date-only lessons do not include an intrinsic time; use source file mtime
            # so the UI can still present an unambiguous freshness timestamp.
            event_timestamp_utc = source_mtime_utc
        category_label = _extract_field(
            re.compile(r"\*\*Category\*\*:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
            text,
        )
        category_label = frontmatter.get("category") or category_label
        severity = _extract_field(
            re.compile(r"\*\*Severity\*\*:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
            text,
        )
        severity = frontmatter.get("severity") or severity
        summary = _extract_summary(text)
        if not summary:
            summary = frontmatter.get("description", "")
        tags = _extract_tags(text)

        lessons.append(
            {
                "id": item_id,
                "title": title,
                "date": date_raw or "",
                "category": category_label or category,
                "severity": severity.upper() if severity else "",
                "summary": summary,
                "tags": tags,
                "content": text.strip(),
                "file": source_path,
                "event_timestamp_utc": event_timestamp_utc,
                "source_mtime_utc": source_mtime_utc,
                "indexed_at_utc": indexed_at_utc,
                "_date_sort": date_obj.isoformat() if date_obj else "",
            }
        )

    # Sort by date desc if available; fallback keeps stable ordering
    lessons.sort(
        key=lambda lesson: lesson.get("_date_sort") or "",
        reverse=True,
    )

    # Remove internal sort key
    for lesson in lessons:
        lesson.pop("_date_sort", None)

    return lessons


def _build_lessons_page(lessons: list[dict]) -> str:
    max_items = int(os.getenv("LESSONS_INDEX_LIMIT", "120"))
    items = lessons[:max_items]
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for lesson in items:
        title = lesson.get("title") or lesson.get("id") or "Lesson"
        severity = lesson.get("severity") or "INFO"
        date = lesson.get("date") or ""
        category = lesson.get("category") or ""
        source = lesson.get("file") or ""
        url = f"https://github.com/IgorGanapolsky/trading/blob/main/{source}" if source else ""
        title_html = escape(title)
        severity_html = escape(severity)
        date_html = escape(date)
        category_html = escape(category)
        if url:
            title_cell = f'<a href="{url}">{title_html}</a>'
        else:
            title_cell = title_html
        rows.append(
            f"<tr><td>{title_cell}</td><td>{severity_html}</td><td>{date_html}</td><td>{category_html}</td></tr>"
        )

    if not rows:
        rows.append("<tr><td>No lessons available</td><td>--</td><td>--</td><td>--</td></tr>")

    item_list = []
    for idx, lesson in enumerate(items, 1):
        title = lesson.get("title") or lesson.get("id") or "Lesson"
        source = lesson.get("file") or ""
        url = (
            f"https://github.com/IgorGanapolsky/trading/blob/main/{source}"
            if source
            else "https://igorganapolsky.github.io/trading/lessons/"
        )
        item_list.append(
            {
                "@type": "ListItem",
                "position": idx,
                "name": title,
                "url": url,
            }
        )

    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "@id": "https://igorganapolsky.github.io/trading/lessons/#itemlist",
        "name": "AI Trading System Lessons Learned",
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "numberOfItems": len(items),
        "itemListElement": item_list,
    }

    content = [
        "---",
        "layout: default",
        'title: "Lessons Learned Index"',
        'description: "Structured index of lessons learned from the autonomous AI trading system."',
        "---",
        "",
        "<h1>Lessons Learned Index</h1>",
        "<p>A structured, crawlable index of lessons learned from the AI trading system.</p>",
        "<p>This page is auto-generated to keep semantic signals consistent and up to date.</p>",
        f"<p><strong>Last updated:</strong> {escape(updated)}</p>",
        "<p><strong>Canonical JSON index:</strong></p>",
        "<ul>",
        "<li><code>/trading/data/rag/lessons_query.json</code> (GitHub Pages cache)</li>",
        '<li><a href="https://raw.githubusercontent.com/IgorGanapolsky/trading/main/data/rag/lessons_query.json">raw GitHub JSON index</a></li>',
        "</ul>",
        "<h2>Latest Lessons</h2>",
        "<table>",
        "<thead><tr><th>Lesson</th><th>Severity</th><th>Date</th><th>Category</th></tr></thead>",
        "<tbody>",
        *rows,
        "</tbody>",
        "</table>",
        '<script type="application/ld+json">',
        json.dumps(schema, indent=2),
        "</script>",
        "",
    ]
    return "\n".join(content)


def main() -> int:
    lessons = build_index()
    payload = json.dumps(lessons, indent=2)
    for output_path in OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload)
        print(f"Wrote {len(lessons)} lessons to {output_path}")

    LESSONS_PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LESSONS_PAGE_PATH.write_text(_build_lessons_page(lessons))
    print(f"Updated lessons index page: {LESSONS_PAGE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
