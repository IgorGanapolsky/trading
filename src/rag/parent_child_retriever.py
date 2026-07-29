"""Parent-Child Retriever for RAG.

Indexes small, dense child chunks for high-vector similarity matching,
while linking back to full parent document/lesson context when retrieved.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChildChunk:
    chunk_id: str
    parent_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParentDocument:
    parent_id: str
    title: str
    full_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ParentChildRetriever:
    """Parent-Child chunk retriever linking dense sub-chunks to parent lessons."""

    def __init__(self, chunk_size_chars: int = 300):
        self.chunk_size_chars = chunk_size_chars
        self.parents: dict[str, ParentDocument] = {}
        self.children: list[ChildChunk] = []

    def add_document(self, parent_id: str, title: str, full_content: str, metadata: dict[str, Any] | None = None) -> None:
        meta = metadata or {}
        parent = ParentDocument(parent_id=parent_id, title=title, full_content=full_content, metadata=meta)
        self.parents[parent_id] = parent

        # Create child chunks
        text = full_content.strip()
        if len(text) <= self.chunk_size_chars:
            child = ChildChunk(chunk_id=f"{parent_id}_c0", parent_id=parent_id, text=text, metadata=meta)
            self.children.append(child)
        else:
            sentences = [s.strip() for s in text.split("\n") if s.strip()]
            curr_chunk = []
            curr_len = 0
            chunk_idx = 0
            for s in sentences:
                if curr_len + len(s) > self.chunk_size_chars and curr_chunk:
                    chunk_text = " ".join(curr_chunk)
                    child = ChildChunk(chunk_id=f"{parent_id}_c{chunk_idx}", parent_id=parent_id, text=chunk_text, metadata=meta)
                    self.children.append(child)
                    chunk_idx += 1
                    curr_chunk = [s]
                    curr_len = len(s)
                else:
                    curr_chunk.append(s)
                    curr_len += len(s)
            if curr_chunk:
                chunk_text = " ".join(curr_chunk)
                child = ChildChunk(chunk_id=f"{parent_id}_c{chunk_idx}", parent_id=parent_id, text=chunk_text, metadata=meta)
                self.children.append(child)

    def retrieve_parent_context(self, matched_parent_ids: list[str]) -> list[ParentDocument]:
        """Resolve matched child hits back to full parent documents."""
        res = []
        for pid in matched_parent_ids:
            if pid in self.parents:
                res.append(self.parents[pid])
        return res
