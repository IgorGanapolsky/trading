"""
Lessons Learned Contract (RAG/ML Regression Guard).

This module turns "lessons learned" markdown into machine-checkable constraints.
It is intentionally lightweight (regex-based) so it can run in CI without heavy deps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "id": re.compile(r"^\*\*ID\*\*:\s*(?P<value>\S+)\s*$", re.MULTILINE),
    "date": re.compile(r"^\*\*Date\*\*:\s*(?P<value>.+?)\s*$", re.MULTILINE),
    "severity": re.compile(r"^\*\*Severity\*\*:\s*(?P<value>\w+)\s*$", re.MULTILINE),
    "category": re.compile(r"^\*\*Category\*\*:\s*(?P<value>.+?)\s*$", re.MULTILINE),
    "impact": re.compile(r"^\*\*Impact\*\*:\s*(?P<value>.+?)\s*$", re.MULTILINE),
}


@dataclass(frozen=True)
class LessonDoc:
    path: Path
    content: str
    lesson_id: str | None
    date: str | None
    severity: str | None
    category: str | None
    impact: str | None

    def has_section(self, header_text: str) -> bool:
        # Match "## Header" (or deeper) case-insensitively.
        pattern = re.compile(
            rf"^##+\s+{re.escape(header_text)}\s*$", re.IGNORECASE | re.MULTILINE
        )
        return bool(pattern.search(self.content))

    def has_any_section_prefix(self, header_prefix: str) -> bool:
        pattern = re.compile(rf"^##+\s+{re.escape(header_prefix)}", re.IGNORECASE | re.MULTILINE)
        return bool(pattern.search(self.content))

    def referenced_repo_paths(self) -> list[str]:
        """
        Extract backticked repo paths like `src/foo.py`.

        We keep this conservative to avoid false positives on code fragments.
        """
        candidates = re.findall(r"`([^`\n]+)`", self.content)
        repo_roots = ("src/", "scripts/", "tests/", "config/", "docs/", "rag_knowledge/")
        out: list[str] = []
        for c in candidates:
            c = c.strip()
            if c.startswith(repo_roots):
                out.append(c)
        return sorted(set(out))

    def inferred_id(self) -> str | None:
        """
        Infer ID from filename if missing, e.g. ll_010_something.md -> ll_010
        """
        if self.lesson_id:
            return self.lesson_id
        m = re.match(r"^(ll_\d{3})\b", self.path.name)
        return m.group(1) if m else None

    def has_impact_any_form(self) -> bool:
        # Either explicit **Impact** field OR an "Impact" section.
        return self.impact is not None or self.has_section("Impact")


def parse_lesson_markdown(path: Path) -> LessonDoc:
    content = path.read_text(encoding="utf-8")

    def _extract(field: str) -> str | None:
        m = _FIELD_PATTERNS[field].search(content)
        return m.group("value").strip() if m else None

    doc = LessonDoc(
        path=path,
        content=content,
        lesson_id=_extract("id"),
        date=_extract("date"),
        severity=(_extract("severity") or None),
        category=_extract("category"),
        impact=_extract("impact"),
    )
    # Infer ID from filename if missing.
    if doc.lesson_id is None:
        inferred = re.match(r"^(ll_\d{3})\b", path.name)
        if inferred:
            return LessonDoc(
                path=doc.path,
                content=doc.content,
                lesson_id=inferred.group(1),
                date=doc.date,
                severity=doc.severity,
                category=doc.category,
                impact=doc.impact,
            )
    return doc


def iter_lessons(lessons_dir: Path) -> Iterable[LessonDoc]:
    for md in sorted(lessons_dir.glob("*.md")):
        yield parse_lesson_markdown(md)


def normalize_severity(sev: str | None) -> str | None:
    if sev is None:
        return None
    sev = sev.strip().upper()
    if sev in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        return sev
    return sev

