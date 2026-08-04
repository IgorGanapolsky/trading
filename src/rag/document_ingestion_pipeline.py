"""9-Stage Document Ingestion, Deduplication, & Versioning Pipeline.

Provides automated document parsing (messy multi-format via
``src.research.messy_document_parser``), SHA256 content deduplication,
unicode normalization, incremental update manifest tracking, and
re-indexing version control.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.rag.acl import attach_acl_metadata
from src.rag.chunking import ChunkStrategy, chunk_document

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = ROOT / "data" / "audit" / "ingestion_version_manifest.json"

# Binary / messy extensions routed through the multi-format cascade
_MESSY_SUFFIXES = frozenset(
    {
        ".pdf",
        ".html",
        ".htm",
        ".xhtml",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".webp",
        ".gif",
    }
)


@dataclass(frozen=True)
class IngestedDocument:
    lesson_id: str
    file_path: str
    sha256_hash: str
    version: int
    normalized_content: str
    metadata: dict[str, Any]
    is_duplicate: bool
    chunks: list[dict[str, Any]] = field(default_factory=list)


class DocumentIngestionPipeline:
    """Manages document parsing, deduplication, normalization, and versioning."""

    def __init__(
        self,
        manifest_file: Path | None = None,
        *,
        chunk_strategy: ChunkStrategy = "hierarchical",
    ):
        self.manifest_path = manifest_file or MANIFEST_FILE
        self.manifest = self._load_manifest()
        self.chunk_strategy = chunk_strategy

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            try:
                with self.manifest_path.open("r", encoding="utf-8") as h:
                    return json.load(h)
            except Exception as e:
                logger.warning("Failed to load manifest file: %s", e)
        return {"documents": {}, "total_ingested": 0, "last_updated": 0.0}

    def compute_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def normalize_text(self, text: str) -> str:
        """Unicode normalization and secret stripping."""
        # 1. NFKC Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # 2. Secret & Token Stripping
        text = re.sub(r"sk-[a-zA-Z0-9_-]{24,}", "[REDACTED_SECRET]", text)
        text = re.sub(r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]", text)

        # 3. Whitespace normalization
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    def extract_from_path(
        self,
        file_path: Path,
        *,
        require_quality_pass: bool = False,
    ) -> dict[str, Any]:
        """Extract text from a filesystem path (Markdown or messy formats).

        Returns a payload with text/markdown/backend/quality. Does not write
        the manifest — call ``ingest_document`` / ``ingest_file`` for that.
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix in _MESSY_SUFFIXES or suffix == ".pdf":
            from src.research.messy_document_parser import parse_document

            parsed = parse_document(file_path, require_quality_pass=require_quality_pass)
            body = parsed.markdown or parsed.text
            return {
                "text": body,
                "backend": parsed.backend,
                "format": parsed.format,
                "quality": asdict(parsed.quality) if parsed.quality else {},
                "tables": len(parsed.tables),
                "warnings": list(parsed.warnings),
                "content_hash_short": parsed.content_hash,
                "parse_metadata": parsed.metadata,
            }

        # Clean text/markdown path
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        return {
            "text": raw,
            "backend": "plaintext",
            "format": "markdown" if suffix in {".md", ".markdown"} else "text",
            "quality": {"passed": True, "char_count": len(raw)},
            "tables": 0,
            "warnings": [],
            "content_hash_short": "",
            "parse_metadata": {},
        }

    def _severity_from_text(self, text: str) -> str:
        m = re.search(
            r"severity\s*[:#]?\s*(critical|high|medium|low)",
            text[:2000],
            re.IGNORECASE,
        )
        return m.group(1).upper() if m else "MEDIUM"

    def ingest_document(self, file_path: Path, raw_content: str) -> IngestedDocument:
        norm_content = self.normalize_text(raw_content)
        content_hash = self.compute_sha256(norm_content)

        # Extract lesson ID from filename or content
        match = re.search(r"LL-\d+", file_path.name)
        lesson_id = match.group(0) if match else file_path.stem

        existing = self.manifest["documents"].get(lesson_id, {})
        prev_hash = existing.get("sha256_hash", "")
        prev_version = existing.get("version", 0)

        is_duplicate = content_hash == prev_hash
        version = prev_version if is_duplicate else prev_version + 1

        severity = self._severity_from_text(norm_content)
        chunks = [
            c.to_dict()
            for c in chunk_document(
                norm_content,
                strategy=self.chunk_strategy,
                prefix=re.sub(r"[^a-zA-Z0-9_-]", "_", lesson_id)[:24],
            )
        ]
        metadata = attach_acl_metadata(
            {
                "file_name": file_path.name,
                "char_count": len(norm_content),
                "line_count": len(norm_content.splitlines()),
                "severity": severity,
                "chunk_strategy": self.chunk_strategy,
                "chunk_count": len(chunks),
            },
            severity=severity,
            text=norm_content[:800],
        )

        doc = IngestedDocument(
            lesson_id=lesson_id,
            file_path=str(file_path),
            sha256_hash=content_hash,
            version=version,
            normalized_content=norm_content,
            metadata=metadata,
            is_duplicate=is_duplicate,
            chunks=chunks,
        )

        if not is_duplicate:
            self.manifest["documents"][lesson_id] = {
                "sha256_hash": content_hash,
                "version": version,
                "file_path": str(file_path),
                "metadata": metadata,
                "chunk_count": len(chunks),
            }
            self.manifest["total_ingested"] = len(self.manifest["documents"])
            self.save_manifest()

        return doc

    def ingest_file(
        self,
        file_path: Path | str,
        *,
        require_quality_pass: bool = False,
    ) -> IngestedDocument:
        """End-to-end: extract (messy or clean) → normalize → dedup → version.

        For PDFs/HTML/images uses ``messy_document_parser``. Quality failures
        still produce an IngestedDocument with empty/partial text unless
        ``require_quality_pass=True`` (then ValueError).
        """
        file_path = Path(file_path)
        extracted = self.extract_from_path(file_path, require_quality_pass=require_quality_pass)
        doc = self.ingest_document(file_path, extracted.get("text") or "")
        # Attach parse provenance without breaking frozen dataclass consumers
        enriched_meta = {
            **doc.metadata,
            "parse_backend": extracted.get("backend"),
            "parse_format": extracted.get("format"),
            "parse_tables": extracted.get("tables"),
            "parse_quality": extracted.get("quality"),
            "parse_warnings": extracted.get("warnings"),
        }
        # Rebuild with enriched metadata (frozen dataclass)
        doc = IngestedDocument(
            lesson_id=doc.lesson_id,
            file_path=doc.file_path,
            sha256_hash=doc.sha256_hash,
            version=doc.version,
            normalized_content=doc.normalized_content,
            metadata=enriched_meta,
            is_duplicate=doc.is_duplicate,
            chunks=doc.chunks,
        )
        if not doc.is_duplicate and doc.lesson_id in self.manifest["documents"]:
            self.manifest["documents"][doc.lesson_id]["metadata"] = enriched_meta
            self.save_manifest()
        return doc

    def save_manifest(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("w", encoding="utf-8") as h:
            json.dump(self.manifest, h, indent=2)
