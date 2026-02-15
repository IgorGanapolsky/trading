"""
Helpers for publishing SEO-friendly blog content across:
- GitHub Pages (Jekyll)
- Dev.to (canonical back to GH Pages)
- LinkedIn/X (link back to canonical)

Keep this dependency-free (no PyYAML) so it can run in CI jobs that only
install minimal requirements.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SITE_BASE = "https://igorganapolsky.github.io/trading"

_DATE_YYYY_MM_DD = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})")


def _extract_ymd(date_str: str) -> tuple[str, str, str]:
    match = _DATE_YYYY_MM_DD.match((date_str or "").strip())
    if not match:
        raise ValueError(f"Invalid date (expected YYYY-MM-DD*): {date_str!r}")
    return match.group("y"), match.group("m"), match.group("d")


def canonical_url_for_post(date_str: str, slug: str, *, site_base: str = SITE_BASE) -> str:
    """Canonical URL for Jekyll posts under permalink /:year/:month/:day/:title/."""
    year, month, day = _extract_ymd(date_str)
    clean_slug = (slug or "").strip().strip("/")
    if not clean_slug:
        raise ValueError("slug must be non-empty")
    return f"{site_base}/{year}/{month}/{day}/{clean_slug}/"


def canonical_url_for_post_file(path: str | Path, *, site_base: str = SITE_BASE) -> str:
    """
    Canonical URL for a Jekyll post file like:
      docs/_posts/2026-02-14-lessons-learned.md
      docs/_posts/2026-02-14-rlhf-win-1530.md
    """
    p = Path(path)
    stem = p.stem
    if len(stem) < 12 or stem[4] != "-" or stem[7] != "-" or stem[10] != "-":
        raise ValueError(f"Unsupported post filename (expected YYYY-MM-DD-*.md): {p.name!r}")
    date_str = stem[:10]
    slug = stem[11:]
    return canonical_url_for_post(date_str, slug, site_base=site_base)


def canonical_url_for_collection_item(
    collection: str, stem: str, *, site_base: str = SITE_BASE
) -> str:
    """Canonical URL for Jekyll collections like /reports/:name/ or /discoveries/:name/."""
    clean_collection = (collection or "").strip().strip("/").lower()
    clean_stem = (stem or "").strip().strip("/")
    if not clean_collection:
        raise ValueError("collection must be non-empty")
    if not clean_stem:
        raise ValueError("stem must be non-empty")
    return f"{site_base}/{clean_collection}/{clean_stem}/"


def truncate_meta_description(text: str, *, max_chars: int = 160) -> str:
    """Collapse whitespace and truncate to a safe meta description length."""
    collapsed = re.sub(r"\s+", " ", (text or "").strip())
    if len(collapsed) <= max_chars:
        return collapsed

    # Prefer truncating at a word boundary.
    snippet = collapsed[: max_chars + 1]
    snippet = snippet.rsplit(" ", 1)[0].rstrip(" ,;:-")
    if not snippet:
        snippet = collapsed[:max_chars].rstrip(" ,;:-")
    return f"{snippet}..."


def render_frontmatter(
    meta: dict[str, Any], *, questions: list[dict[str, str]] | None = None
) -> str:
    """
    Render Jekyll front matter as YAML without external deps.

    Uses JSON string encoding for safety (YAML is a superset of JSON), which
    prevents accidental YAML syntax breaks from quotes/colons/newlines.
    """
    lines: list[str] = ["---"]

    for key, value in meta.items():
        if value is None:
            continue

        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
            continue
        if isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
            continue
        if isinstance(value, str):
            lines.append(f"{key}: {json.dumps(value)}")
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, bool):
                    lines.append(f"  - {'true' if item else 'false'}")
                elif isinstance(item, (int, float)):
                    lines.append(f"  - {item}")
                elif isinstance(item, str):
                    lines.append(f"  - {json.dumps(item)}")
                else:
                    raise TypeError(f"Unsupported list item type for {key!r}: {type(item)}")
            continue

        raise TypeError(f"Unsupported frontmatter value type for {key!r}: {type(value)}")

    if questions:
        lines.append("faq: true")
        lines.append("questions:")
        for q in questions:
            question = (q.get("question") or "").strip()
            answer = (q.get("answer") or "").strip()
            if not question or not answer:
                raise ValueError(f"Invalid FAQ item (requires question+answer): {q!r}")
            lines.append(f"  - question: {json.dumps(question)}")
            lines.append(f"    answer: {json.dumps(answer)}")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)
