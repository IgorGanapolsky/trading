"""9-Stage Document Ingestion, Deduplication, & Versioning Pipeline.

Provides automated document parsing, SHA256 content deduplication, unicode normalization,
incremental update manifest tracking, and re-indexing version control.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = ROOT / "data" / "audit" / "ingestion_version_manifest.json"


@dataclass(frozen=True)
class IngestedDocument:
    lesson_id: str
    file_path: str
    sha256_hash: str
    version: int
    normalized_content: str
    metadata: dict[str, Any]
    is_duplicate: bool


class DocumentIngestionPipeline:
    """Manages document parsing, deduplication, normalization, and versioning."""

    def __init__(self, manifest_file: Path | None = None):
        self.manifest_path = manifest_file or MANIFEST_FILE
        self.manifest = self._load_manifest()

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

        metadata = {
            "file_name": file_path.name,
            "char_count": len(norm_content),
            "line_count": len(norm_content.splitlines()),
        }

        doc = IngestedDocument(
            lesson_id=lesson_id,
            file_path=str(file_path),
            sha256_hash=content_hash,
            version=version,
            normalized_content=norm_content,
            metadata=metadata,
            is_duplicate=is_duplicate,
        )

        if not is_duplicate:
            self.manifest["documents"][lesson_id] = {
                "sha256_hash": content_hash,
                "version": version,
                "file_path": str(file_path),
                "metadata": metadata,
            }
            self.manifest["total_ingested"] = len(self.manifest["documents"])
            self.save_manifest()

        return doc

    def save_manifest(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("w", encoding="utf-8") as h:
            json.dump(self.manifest, h, indent=2)
