"""Context re-positioning for RAG lessons.

Reorders and diversifies lessons based on semantic relevance, recency, and severity.
This is a lightweight, dependency-free approximation of "semantic re-positioning"
to keep the most relevant signals close and reduce noisy/duplicative context.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "your",
    "you",
    "our",
    "are",
    "was",
    "were",
    "why",
    "how",
    "what",
    "when",
    "where",
    "who",
    "which",
    "about",
    "after",
    "before",
    "they",
    "them",
    "their",
    "then",
    "than",
    "but",
    "not",
    "can",
    "could",
    "should",
    "would",
    "will",
    "just",
    "does",
    "did",
    "had",
    "has",
    "have",
    "it",
    "its",
    "be",
    "as",
    "at",
    "by",
    "or",
    "if",
    "in",
    "on",
    "to",
    "of",
}

_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M %Z",
    "%Y-%m-%d %H:%M",
    "%B %d, %Y",
    "%b %d, %Y",
)

_MONTHS = {
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


@dataclass
class _Candidate:
    lesson: dict
    score: float
    tokens: set[str]


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 and t not in _STOPWORDS]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _extract_date(lesson: dict) -> datetime | None:
    # Direct date field
    date_val = lesson.get("date") or lesson.get("created_at")
    parsed = _parse_date(date_val if isinstance(date_val, str) else None)
    if parsed:
        return parsed

    # Look for "**Date**:" inside content
    content = lesson.get("content") or lesson.get("snippet") or ""
    match = re.search(r"\*\*Date\*\*:\s*([^\n]+)", content)
    if match:
        parsed = _parse_date(match.group(1).strip())
        if parsed:
            return parsed

    # Parse from id or file name (e.g. jan31, 20260106)
    fallback = str(lesson.get("id") or lesson.get("file") or "")
    if fallback:
        match = re.search(
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{1,2})", fallback.lower()
        )
        if match:
            month = _MONTHS[match.group(1)]
            day = int(match.group(2))
            year = datetime.now().year
            try:
                candidate = datetime(year, month, day)
                if candidate > datetime.now():
                    candidate = datetime(year - 1, month, day)
                return candidate
            except ValueError:
                pass
        match = re.search(r"(\d{8})", fallback)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y%m%d")
            except ValueError:
                pass
    return None


def _severity_weight(severity: str) -> float:
    sev = (severity or "").upper()
    return {
        "CRITICAL": 1.35,
        "HIGH": 1.2,
        "MEDIUM": 1.0,
        "LOW": 0.9,
    }.get(sev, 1.0)


def _structure_bonus(content: str) -> float:
    if not content:
        return 0.0
    bonus = 0.0
    headings = [
        "## prevention",
        "## action",
        "## solution",
        "## fix",
        "## root cause",
        "## impact",
        "## lesson",
    ]
    lowered = content.lower()
    for head in headings:
        if head in lowered:
            bonus += 0.04
    return min(bonus, 0.16)


def _recency_bonus(lesson_date: datetime | None, query_terms: set[str]) -> float:
    if not lesson_date:
        return 0.0
    days_old = (datetime.now() - lesson_date).days
    if days_old < 0:
        return 0.0

    wants_recent = any(term in {"latest", "last", "recent", "new"} for term in query_terms)
    if days_old <= 7:
        return 0.24 if wants_recent else 0.12
    if days_old <= 30:
        return 0.18 if wants_recent else 0.08
    if days_old <= 90:
        return 0.12 if wants_recent else 0.05
    return 0.0


def _base_score(lesson: dict) -> float:
    raw = lesson.get("score")
    try:
        raw_val = float(raw)
    except (TypeError, ValueError):
        raw_val = 0.0
    if math.isnan(raw_val) or math.isinf(raw_val):
        return 0.0
    return max(0.0, min(raw_val, 2.0))


def _keyword_score(text: str, query_terms: Iterable[str]) -> float:
    if not text:
        return 0.0
    lowered = text.lower()
    hits = 0
    for term in query_terms:
        if term in lowered:
            hits += min(lowered.count(term), 3)
    if not query_terms:
        return 0.0
    return hits / max(len(list(query_terms)), 1)


def reposition_lessons(query: str, lessons: list[dict], top_k: int) -> list[dict]:
    """Re-rank lessons to prioritize relevance and reduce duplication.

    Args:
        query: User query.
        lessons: List of lesson dicts (from LessonsLearnedRAG).
        top_k: Max results to return.

    Returns:
        Reordered lesson list (with context_score attached).
    """
    if not lessons:
        return []

    enabled = os.getenv("CONTEXT_REPOSITIONING", "true").lower() in {"1", "true", "yes"}
    if not enabled:
        return lessons[:top_k]

    threshold_env = os.getenv("CONTEXT_DIVERSITY_THRESHOLD", "0.72")
    try:
        diversity_threshold = float(threshold_env)
    except ValueError:
        diversity_threshold = 0.72

    query_terms = set(_tokenize(query))
    query_lower = query.lower().strip()

    candidates: list[_Candidate] = []
    for lesson in lessons:
        content = lesson.get("content") or lesson.get("snippet") or ""
        title = lesson.get("title") or lesson.get("id") or ""
        text = " ".join([title, content, str(lesson.get("id", ""))])

        base = _base_score(lesson)
        keyword = _keyword_score(text, query_terms)
        phrase_bonus = 0.25 if query_lower and query_lower in text.lower() else 0.0
        severity_weight = _severity_weight(lesson.get("severity", ""))
        structure = _structure_bonus(content)
        recency = _recency_bonus(_extract_date(lesson), query_terms)

        score = (base * 0.55) + (keyword * 0.9) + phrase_bonus + structure + recency
        score *= severity_weight

        token_source = " ".join([title, str(lesson.get("id", ""))])
        tokens = set(_tokenize(token_source))

        lesson["context_score"] = round(score, 6)
        candidates.append(_Candidate(lesson=lesson, score=score, tokens=tokens))

    candidates.sort(key=lambda c: c.score, reverse=True)

    selected: list[_Candidate] = []
    for candidate in candidates:
        if len(selected) >= top_k:
            break
        if not selected:
            selected.append(candidate)
            continue

        similar = False
        for kept in selected:
            if not candidate.tokens or not kept.tokens:
                continue
            intersection = candidate.tokens & kept.tokens
            union = candidate.tokens | kept.tokens
            similarity = len(intersection) / max(len(union), 1)
            if similarity >= diversity_threshold:
                similar = True
                break
        if not similar:
            selected.append(candidate)

    if len(selected) < top_k:
        selected_ids = {c.lesson.get("id") for c in selected}
        for candidate in candidates:
            if len(selected) >= top_k:
                break
            if candidate.lesson.get("id") in selected_ids:
                continue
            selected.append(candidate)

    return [c.lesson for c in selected[:top_k]]
