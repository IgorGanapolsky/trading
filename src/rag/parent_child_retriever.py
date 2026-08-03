"""Parent-Child Context Expander for Agentic RAG.

Matches small child chunks during similarity search, then retrieves full parent
lesson document context to ensure complete code and rule execution integrity.
"""

from __future__ import annotations

import logging
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


class ParentChildRetriever:
    """Expands small matched child chunks to full parent lesson context."""

    def __init__(self, parent_store: dict[str, str] | None = None, chunk_size_chars: int = 300):
        self.parent_store = parent_store or {}
        self.parent_titles: dict[str, str] = {}
        self.chunk_size_chars = chunk_size_chars
        self.children: list[dict[str, Any]] = []

    def add_document(
        self, parent_id: str, title: str, full_content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        meta = metadata or {}
        self.parent_store[parent_id] = full_content
        self.parent_titles[parent_id] = title
        text = full_content.strip()
        lines = [s.strip() for s in text.split("\n") if s.strip()]
        curr = []
        curr_len = 0
        idx = 0
        for line in lines:
            if curr_len + len(line) > self.chunk_size_chars and curr:
                chunk_txt = " ".join(curr)
                self.children.append(
                    {
                        "id": f"{parent_id}_c{idx}",
                        "parent_id": parent_id,
                        "title": title,
                        "content": chunk_txt,
                        **meta,
                    }
                )
                idx += 1
                curr = [line]
                curr_len = len(line)
            else:
                curr.append(line)
                curr_len += len(line)
        if curr:
            chunk_txt = " ".join(curr)
            self.children.append(
                {
                    "id": f"{parent_id}_c{idx}",
                    "parent_id": parent_id,
                    "title": title,
                    "content": chunk_txt,
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
