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


class ParentChildRetriever:
    """Expands small matched child chunks to full parent lesson context."""

    def __init__(self, parent_store: dict[str, str] | None = None):
        self.parent_store = parent_store or {}

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
