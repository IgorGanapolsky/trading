"""Parse ExplainX /trending HTML by the page's own score field.

Their ranking is *their* page views, not trading ROI. Zero parsed items is
UNAVAILABLE — never invent TF-IDF scores or hardcoded titles.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

TRENDING_URL = "https://explainx.ai/trending"
UNAVAILABLE = "UNAVAILABLE"
USER_AGENT = "trading-lab-explainx-mapper/1.0"
_PUSH_DOUBLE_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)')
_PUSH_SINGLE_RE = re.compile(
    r"self\.__next_f\.push\(\[\s*1\s*,\s*'((?:\\.|[^'\\])*)'\s*,?\s*\]\s*\)",
    re.S,
)


@dataclass(frozen=True)
class TrendingItem:
    rank: int
    name: str
    href: str
    score: int
    type: str
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExplainXParseError(RuntimeError):
    """HTML had no ranked items, or the URL scheme is refused."""


def _assert_http_url(url: str) -> None:
    scheme = urlparse(url).scheme.lower()
    if scheme not in {"https", "http"}:
        raise ExplainXParseError(f"refusing non-http ExplainX URL scheme {scheme!r}")


def _unescape_js_double(payload: str) -> str | None:
    try:
        decoded = json.loads(f'"{payload}"')
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return decoded if isinstance(decoded, str) else None


def _unescape_js_single(payload: str) -> str | None:
    """Prettier may rewrite the RSC push as a single-quoted JS string."""

    try:
        decoded = json.loads('"' + payload.replace('"', '\\"') + '"')
    except (json.JSONDecodeError, ValueError, TypeError):
        decoded = payload.replace("\\'", "'").replace('\\"', '"')
    return decoded if isinstance(decoded, str) else None


def _extract_json_array(blob: str, start: int) -> Any | None:
    depth = 0
    end = None
    for index, char in enumerate(blob[start:], start):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        return None
    try:
        parsed = json.loads(blob[start:end])
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return parsed


def _items_from_decoded(decoded: str) -> list[dict[str, Any]]:
    marker = '"items":'
    found = decoded.find(marker)
    if found < 0:
        return []
    start = decoded.find("[", found)
    if start < 0:
        return []
    parsed = _extract_json_array(decoded, start)
    if not isinstance(parsed, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in parsed:
        if isinstance(row, dict) and "score" in row and "name" in row:
            rows.append(row)
    return rows


def parse_trending_html(html: str) -> list[TrendingItem]:
    """Return items ranked by parsed score. Empty input → empty list (fail-closed)."""

    text = html or ""
    candidates: list[dict[str, Any]] = []

    def _consider(decoded: str | None) -> None:
        nonlocal candidates
        if not decoded:
            return
        rows = _items_from_decoded(decoded)
        if len(rows) > len(candidates):
            candidates = rows

    for match in _PUSH_DOUBLE_RE.finditer(text):
        _consider(_unescape_js_double(match.group(1)))
    for match in _PUSH_SINGLE_RE.finditer(text):
        _consider(_unescape_js_single(match.group(1)))
    if not candidates:
        # Formatted fixtures and already-decoded blobs expose "items": directly.
        candidates = _items_from_decoded(text)

    ranked: list[TrendingItem] = []
    seen: set[tuple[str, str, int]] = set()
    for row in sorted(
        candidates,
        key=lambda item: (-int(item.get("score") or 0), str(item.get("href") or "")),
    ):
        try:
            score = int(row["score"])
        except (TypeError, ValueError, KeyError):
            continue
        name = str(row.get("name") or "").strip()
        href = str(row.get("href") or "").strip()
        if not name or score < 0:
            continue
        key = (name, href, score)
        if key in seen:
            continue
        seen.add(key)
        ranked.append(
            TrendingItem(
                rank=len(ranked) + 1,
                name=name,
                href=href,
                score=score,
                type=str(row.get("type") or row.get("typeLabel") or "").strip().lower(),
                description=str(row.get("description") or "").strip(),
            )
        )
    return ranked


def fetch_trending_html(
    url: str = TRENDING_URL,
    *,
    timeout: float = 20.0,
) -> str:
    _assert_http_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        return response.read().decode("utf-8", errors="replace")
