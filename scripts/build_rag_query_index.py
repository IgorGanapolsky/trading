#!/usr/bin/env python3
"""Build a compact JSON index for the RAG query UI and worker.

Reads rag_knowledge/**/*.md and emits data/rag/lessons_query.json.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

RAG_ROOT = Path("rag_knowledge")
OUTPUT_PATH = Path("data/rag/lessons_query.json")

DATE_PATTERNS = [
    (re.compile(r"\*\*Date\*\*:\s*(.+)$", re.IGNORECASE | re.MULTILINE), "%B %d, %Y"),
    (re.compile(r"\bDate\b:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE), "%Y-%m-%d"),
]


def _extract_field(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _extract_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else fallback


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


def _parse_date(text: str) -> tuple[str, datetime | None]:
    for pattern, fmt in DATE_PATTERNS:
        raw = _extract_field(pattern, text)
        if raw:
            try:
                parsed = datetime.strptime(raw, fmt)
                return raw, parsed
            except ValueError:
                return raw, None
    return "", None


def build_index() -> list[dict]:
    lessons = []
    if not RAG_ROOT.exists():
        return lessons

    for path in sorted(RAG_ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel_path = path.relative_to(RAG_ROOT)
        category = rel_path.parts[0] if rel_path.parts else "general"

        if category == "lessons_learned":
            item_id = path.stem
        else:
            item_id = rel_path.with_suffix("").as_posix()

        title = _extract_title(text, item_id)
        date_raw, date_obj = _parse_date(text)
        category_label = _extract_field(
            re.compile(r"\*\*Category\*\*:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
            text,
        )
        severity = _extract_field(
            re.compile(r"\*\*Severity\*\*:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
            text,
        )
        summary = _extract_summary(text)
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


def main() -> int:
    lessons = build_index()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(lessons, indent=2))
    print(f"Wrote {len(lessons)} lessons to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
