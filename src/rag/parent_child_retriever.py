"""Parent-Child Context Expander for Agentic RAG.

Matches small child chunks during similarity search, then retrieves full parent
lesson document context to ensure complete code and rule execution integrity.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParentChildContext:
    child_chunk_id: str
    parent_lesson_id: str
    parent_title: str
    full_parent_content: str

    @property
    def title(self) -> str:
        return self.parent_title


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)?")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _token_windows(text: str, *, target_tokens: int, overlap_tokens: int) -> list[str]:
    """Split one Markdown section into bounded, overlapping token windows."""
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return []
    if len(tokens) <= target_tokens:
        return [" ".join(tokens)]
    step = max(1, target_tokens - overlap_tokens)
    return [
        " ".join(tokens[start : start + target_tokens])
        for start in range(0, len(tokens), step)
        if tokens[start : start + target_tokens]
    ]


def _markdown_sections(content: str) -> list[tuple[str, str]]:
    """Return heading-aware sections while retaining introductory content."""
    sections: list[tuple[str, str]] = []
    heading_path: list[str] = []
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            sections.append((" > ".join(heading_path) or "Document", text))

    for raw_line in content.splitlines():
        match = _HEADING_RE.match(raw_line.strip())
        if not match:
            if raw_line.strip():
                body.append(raw_line.strip())
            continue
        flush()
        body = []
        level = len(match.group(1))
        heading_path = heading_path[: level - 1]
        heading_path.append(match.group(2).strip())
    flush()
    return sections


class ParentChildRetriever:
    """Index heading-aware child chunks and expand matches to their parent lesson.

    Child chunks are retrieval units; the complete immutable lesson remains the
    evidence unit returned to downstream answer and risk gates.
    """

    def __init__(
        self,
        parent_store: dict[str, str] | None = None,
        chunk_size_chars: int | None = None,
        *,
        target_tokens: int = 320,
        overlap_tokens: int = 48,
    ):
        self.parent_store = parent_store or {}
        self.parent_titles: dict[str, str] = {}
        if chunk_size_chars is not None:
            # Compatibility for callers of the original character-based API.
            target_tokens = max(16, chunk_size_chars // 4)
        self.target_tokens = max(16, target_tokens)
        self.overlap_tokens = min(max(0, overlap_tokens), self.target_tokens // 2)
        self.children: list[dict[str, Any]] = []

    def add_document(
        self, parent_id: str, title: str, full_content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        meta = metadata or {}
        self.parent_store[parent_id] = full_content
        self.parent_titles[parent_id] = title
        self.children = [child for child in self.children if child.get("parent_id") != parent_id]
        idx = 0
        for section_path, section_content in _markdown_sections(full_content):
            for window in _token_windows(
                section_content,
                target_tokens=self.target_tokens,
                overlap_tokens=self.overlap_tokens,
            ):
                chunk_txt = f"{title}\nSection: {section_path}\n{window}".strip()
                self.children.append(
                    {
                        "id": f"{parent_id}_c{idx}",
                        "parent_id": parent_id,
                        "title": title,
                        "section_path": section_path,
                        "content": chunk_txt,
                        **meta,
                    }
                )
                idx += 1
        if idx == 0:
            self.children.append(
                {
                    "id": f"{parent_id}_c0",
                    "parent_id": parent_id,
                    "title": title,
                    "section_path": "Document",
                    "content": title,
                    **meta,
                }
            )

    def retrieve_parent_context(self, matched_parent_ids: list[str]) -> list[ParentChildContext]:
        res = []
        for pid in matched_parent_ids:
            content = self.parent_store.get(pid, "")
            title = self.parent_titles.get(pid, pid)
            res.append(
                ParentChildContext(
                    child_chunk_id=f"{pid}_c0",
                    parent_lesson_id=pid,
                    parent_title=title,
                    full_parent_content=content,
                )
            )
        return res

    def expand_child_to_parent(
        self,
        child_match: dict[str, Any],
    ) -> ParentChildContext:
        child_id = str(child_match.get("id", child_match.get("lesson_id", "N/A")))
        parent_id = str(child_match.get("parent_id", child_id))
        title = str(child_match.get("title", ""))

        parent_content = self.parent_store.get(
            parent_id, str(child_match.get("content", child_match.get("snippet", "")))
        )

        return ParentChildContext(
            child_chunk_id=child_id,
            parent_lesson_id=parent_id,
            parent_title=title,
            full_parent_content=parent_content,
        )

    def get_parent(self, parent_id: str) -> str | None:
        return self.parent_store.get(parent_id)
