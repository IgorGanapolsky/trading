"""World-class chunking strategies for trading RAG.

Strategies:
  - fixed: character windows with overlap
  - recursive: hierarchical separators (headers → paragraphs → sentences)
  - semantic: structure-aware blocks (headers + code fences kept intact)
  - hierarchical: parent section + child chunks (parent-child retrieval)
  - late: embed full doc summary anchor + late-split children (late chunking style)

No external dependencies. Designed for markdown lessons and extracted messy docs.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Literal

ChunkStrategy = Literal["fixed", "recursive", "semantic", "hierarchical", "late"]

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[\*])")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    strategy: str
    index: int
    parent_id: str | None = None
    level: int = 0  # 0=leaf, 1=parent, 2=doc-summary
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "strategy": self.strategy,
            "index": self.index,
            "parent_id": self.parent_id,
            "level": self.level,
            "metadata": self.metadata,
            "char_count": len(self.text),
        }


def _cid(prefix: str, text: str, index: int) -> str:
    digest = hashlib.sha256(f"{prefix}:{index}:{text[:120]}".encode()).hexdigest()[:12]
    return f"{prefix}-{index}-{digest}"


def chunk_fixed(
    text: str, *, size: int = 800, overlap: int = 120, prefix: str = "fx"
) -> list[Chunk]:
    text = (text or "").strip()
    if not text:
        return []
    size = max(100, size)
    overlap = max(0, min(overlap, size // 2))
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + size)
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                Chunk(
                    chunk_id=_cid(prefix, piece, idx),
                    text=piece,
                    strategy="fixed",
                    index=idx,
                    metadata={"start": start, "end": end},
                )
            )
            idx += 1
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def chunk_recursive(
    text: str,
    *,
    size: int = 900,
    overlap: int = 100,
    prefix: str = "rc",
) -> list[Chunk]:
    """Split by headers → blank lines → sentences → fixed fallback."""
    text = (text or "").strip()
    if not text:
        return []
    # Protect code fences
    fences: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        fences.append(m.group(0))
        return f"\n@@FENCE{len(fences) - 1}@@\n"

    protected = _CODE_FENCE_RE.sub(_stash, text)
    parts = re.split(r"\n(?=#{1,6}\s)", protected)
    units: list[str] = []
    for part in parts:
        if len(part) <= size:
            units.append(part)
            continue
        paras = re.split(r"\n\s*\n", part)
        buf = ""
        for para in paras:
            if len(buf) + len(para) + 2 <= size:
                buf = f"{buf}\n\n{para}".strip()
            else:
                if buf:
                    units.append(buf)
                if len(para) <= size:
                    buf = para
                else:
                    for sent in _SENTENCE_SPLIT.split(para):
                        if len(buf) + len(sent) + 1 <= size:
                            buf = f"{buf} {sent}".strip()
                        else:
                            if buf:
                                units.append(buf)
                            if len(sent) > size:
                                units.extend(
                                    c.text for c in chunk_fixed(sent, size=size, overlap=overlap)
                                )
                                buf = ""
                            else:
                                buf = sent
        if buf:
            units.append(buf)

    # Restore fences
    restored: list[str] = []
    for u in units:

        def _restore(m: re.Match[str]) -> str:
            i = int(m.group(1))
            return fences[i] if 0 <= i < len(fences) else m.group(0)

        restored.append(re.sub(r"@@FENCE(\d+)@@", _restore, u).strip())

    chunks: list[Chunk] = []
    for i, piece in enumerate(restored):
        if not piece:
            continue
        chunks.append(
            Chunk(
                chunk_id=_cid(prefix, piece, i),
                text=piece,
                strategy="recursive",
                index=i,
            )
        )
    if overlap > 0 and len(chunks) > 1:
        # light overlap by appending tail of previous
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1].text[-overlap:]
            chunks[i].text = (prev_tail + "\n" + chunks[i].text).strip()
    return chunks


def chunk_semantic(text: str, *, prefix: str = "sm") -> list[Chunk]:
    """Header- and fence-preserving semantic blocks (structure-aware)."""
    text = (text or "").strip()
    if not text:
        return []
    blocks: list[tuple[str, str]] = []
    current_header = "document"
    buf: list[str] = []
    for line in text.splitlines():
        hm = re.match(r"^(#{1,6})\s+(.+)$", line)
        if hm:
            if buf:
                blocks.append((current_header, "\n".join(buf).strip()))
                buf = []
            current_header = hm.group(2).strip()
            buf.append(line)
        else:
            buf.append(line)
    if buf:
        blocks.append((current_header, "\n".join(buf).strip()))

    chunks: list[Chunk] = []
    for i, (header, body) in enumerate(blocks):
        if not body:
            continue
        chunks.append(
            Chunk(
                chunk_id=_cid(prefix, body, i),
                text=body,
                strategy="semantic",
                index=i,
                metadata={"section": header},
            )
        )
    return chunks or chunk_recursive(text, prefix=prefix)


def chunk_hierarchical(text: str, *, child_size: int = 700, prefix: str = "hi") -> list[Chunk]:
    """Parent sections with child chunks for parent-child retrieval."""
    parents = chunk_semantic(text, prefix=f"{prefix}p")
    out: list[Chunk] = []
    child_i = 0
    for p in parents:
        parent = Chunk(
            chunk_id=p.chunk_id,
            text=p.text[:1500],
            strategy="hierarchical",
            index=p.index,
            level=1,
            metadata={**p.metadata, "role": "parent"},
        )
        out.append(parent)
        children = chunk_recursive(p.text, size=child_size, prefix=f"{prefix}c")
        for c in children:
            out.append(
                Chunk(
                    chunk_id=_cid(f"{prefix}c", c.text, child_i),
                    text=c.text,
                    strategy="hierarchical",
                    index=child_i,
                    parent_id=parent.chunk_id,
                    level=0,
                    metadata={"role": "child", "section": p.metadata.get("section")},
                )
            )
            child_i += 1
    return out


def chunk_late(text: str, *, child_size: int = 600, prefix: str = "lt") -> list[Chunk]:
    """Late-chunking style: doc-level anchor + late-split children.

    The anchor is a short summary block (first headers + first 400 chars) used
    for coarse retrieval; children carry fine-grained content.
    """
    text = (text or "").strip()
    if not text:
        return []
    headers = [m.group(0) for m in _HEADER_RE.finditer(text)][:8]
    anchor_body = "\n".join(headers + ["", text[:400]]).strip()
    anchor = Chunk(
        chunk_id=_cid(f"{prefix}a", anchor_body, 0),
        text=anchor_body,
        strategy="late",
        index=0,
        level=2,
        metadata={"role": "doc_anchor"},
    )
    children = chunk_recursive(text, size=child_size, prefix=f"{prefix}c")
    out = [anchor]
    for i, c in enumerate(children):
        out.append(
            Chunk(
                chunk_id=_cid(f"{prefix}c", c.text, i + 1),
                text=c.text,
                strategy="late",
                index=i + 1,
                parent_id=anchor.chunk_id,
                level=0,
                metadata={"role": "late_child"},
            )
        )
    return out


def chunk_document(
    text: str,
    *,
    strategy: ChunkStrategy = "hierarchical",
    **kwargs: Any,
) -> list[Chunk]:
    if strategy == "fixed":
        return chunk_fixed(text, **kwargs)
    if strategy == "recursive":
        return chunk_recursive(text, **kwargs)
    if strategy == "semantic":
        return chunk_semantic(text, **kwargs)
    if strategy == "late":
        return chunk_late(text, **kwargs)
    return chunk_hierarchical(text, **kwargs)
