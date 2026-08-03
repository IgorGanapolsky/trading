"""Production document ingestion for the trading research RAG.

The pipeline deliberately separates extraction from registration:

1. validate the source and route by format;
2. extract text, tables, and provenance with a format-aware parser;
3. fail closed on empty, corrupt, encrypted, or OCR-required documents;
4. normalize and redact secrets;
5. create bounded, terminating, provenance-carrying chunks;
6. register an atomic, content-addressed version in the manifest.

Docling is the preferred backend for PDF, DOCX, and images because it provides
layout-aware OCR and table reconstruction. PyMuPDF is a deterministic fallback
for text-native PDFs. HTML is parsed locally with Beautiful Soup.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import logging
import os
import re
import tempfile
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = ROOT / "data" / "audit" / "ingestion_version_manifest.json"
MANIFEST_SCHEMA_VERSION = 2
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MIN_TEXT_CHARS = 40

TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
HTML_SUFFIXES = {".html", ".htm"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
DOCLING_SUFFIXES = {".pdf", ".docx", *IMAGE_SUFFIXES}
SUPPORTED_SUFFIXES = {*TEXT_SUFFIXES, *HTML_SUFFIXES, ".csv", ".json", *DOCLING_SUFFIXES}
PROMPT_INJECTION_PATTERNS = {
    "instruction_override": re.compile(
        r"\b(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior)?\s*"
        r"(?:system|developer)?\s*(?:instructions?|messages?|prompts?)\b",
        re.IGNORECASE,
    ),
    "tool_execution_request": re.compile(
        r"\b(?:call|invoke|execute|run)\s+(?:the\s+)?(?:tool|function|shell|terminal|command)\b",
        re.IGNORECASE,
    ),
    "trade_execution_request": re.compile(
        r"\b(?:submit|place|execute)\s+(?:a\s+|the\s+)?(?:live\s+)?(?:trade|order)\b",
        re.IGNORECASE,
    ),
    "secret_exfiltration_request": re.compile(
        r"\b(?:reveal|print|send|upload|exfiltrate)\b.{0,80}\b(?:secret|token|password|api key)\b",
        re.IGNORECASE | re.DOTALL,
    ),
}


class IngestionError(RuntimeError):
    """Base class for deterministic ingestion failures."""

    def __init__(self, message: str, *, code: str = "ingestion_error") -> None:
        super().__init__(message)
        self.code = code


class UnsupportedFormatError(IngestionError):
    """Raised when a source format is not explicitly supported."""


class IngestionQualityError(IngestionError):
    """Raised when extraction succeeds technically but fails quality gates."""


class ManifestCorruptionError(IngestionError):
    """Raised instead of silently replacing a corrupt version manifest."""


@dataclass(frozen=True)
class ExtractedTable:
    """A normalized table with source provenance."""

    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    table_index: int
    page_number: int | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        headers = self.headers or tuple(f"column_{i + 1}" for i in range(self.width))
        if not headers:
            return ""
        lines = [f"**Table: {self.title or f'Table {self.table_index + 1}'}**", ""]
        lines.append("| " + " | ".join(_escape_markdown_cell(v) for v in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in self.rows:
            padded = (*row, *("" for _ in range(max(0, len(headers) - len(row)))))
            lines.append(
                "| " + " | ".join(_escape_markdown_cell(v) for v in padded[: len(headers)]) + " |"
            )
        return "\n".join(lines)

    @property
    def width(self) -> int:
        return max([len(self.headers), *(len(row) for row in self.rows)], default=0)


@dataclass(frozen=True)
class ParsedDocument:
    """Structured parser output before deduplication and version registration."""

    source_path: str
    source_sha256: str
    title: str
    media_type: str
    parser: str
    text: str
    tables: tuple[ExtractedTable, ...] = ()
    provenance: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    quality_score: float = 0.0
    ocr_enabled: bool = False


@dataclass(frozen=True)
class DocumentChunk:
    """A bounded retrieval unit with deterministic identity and provenance."""

    chunk_id: str
    text: str
    chunk_index: int
    chunk_type: str
    source_path: str
    source_sha256: str
    parser: str
    page_start: int | None = None
    page_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestedDocument:
    """Registered, normalized document returned to ingestion callers."""

    lesson_id: str
    file_path: str
    sha256_hash: str
    version: int
    normalized_content: str
    metadata: dict[str, Any]
    is_duplicate: bool
    duplicate_of: str | None = None
    parser: str = "raw-text"
    media_type: str = "text/plain"
    quality_score: float = 1.0
    chunks: tuple[DocumentChunk, ...] = ()
    tables: tuple[ExtractedTable, ...] = ()


def _escape_markdown_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class DocumentIngestionPipeline:
    """Format-aware extraction, quality gating, chunking, and versioning."""

    def __init__(
        self,
        manifest_file: Path | None = None,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
        prefer_docling: bool = True,
    ) -> None:
        self.manifest_path = manifest_file or MANIFEST_FILE
        self.max_bytes = max_bytes
        self.min_text_chars = min_text_chars
        self.prefer_docling = prefer_docling
        self.manifest = self._load_manifest()
        self._docling_converter: Any | None = None

    @staticmethod
    def capabilities() -> dict[str, Any]:
        """Return parser availability without importing heavyweight backends."""
        has_docling = importlib.util.find_spec("docling") is not None
        has_pymupdf = importlib.util.find_spec("fitz") is not None
        has_bs4 = importlib.util.find_spec("bs4") is not None
        return {
            "text": True,
            "csv": True,
            "json": True,
            "html": has_bs4,
            "pdf_text": has_docling or has_pymupdf,
            "pdf_layout": has_docling,
            "tables": has_docling or has_pymupdf or has_bs4,
            "scanned_pdf_ocr": has_docling,
            "images_ocr": has_docling,
            "docx": has_docling,
            "backends": {
                "docling": has_docling,
                "pymupdf": has_pymupdf,
                "beautifulsoup4": has_bs4,
            },
        }

    def _new_manifest(self) -> dict[str, Any]:
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "documents": {},
            "hash_index": {},
            "total_ingested": 0,
            "total_unique": 0,
            "last_updated": None,
        }

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return self._new_manifest()
        try:
            with self.manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ManifestCorruptionError(
                f"Ingestion manifest is unreadable: {self.manifest_path}: {exc}",
                code="manifest_corrupt",
            ) from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("documents"), dict):
            raise ManifestCorruptionError(
                f"Ingestion manifest has invalid structure: {self.manifest_path}",
                code="manifest_invalid",
            )
        # Migrate the small v1 manifest in memory. It is persisted on the next write.
        manifest.setdefault("schema_version", MANIFEST_SCHEMA_VERSION)
        manifest.setdefault("hash_index", {})
        for source_key, record in manifest["documents"].items():
            content_hash = record.get("sha256_hash")
            if content_hash:
                manifest["hash_index"].setdefault(content_hash, source_key)
        manifest.setdefault("total_ingested", len(manifest["documents"]))
        manifest.setdefault("total_unique", len(manifest["hash_index"]))
        manifest.setdefault("last_updated", None)
        return manifest

    def compute_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def normalize_text(self, text: str) -> str:
        """Normalize Unicode/whitespace and redact common credential families."""
        normalized, _ = self._normalize_and_redact(text)
        return normalized

    def _normalize_and_redact(self, text: str) -> tuple[str, int]:
        text = unicodedata.normalize("NFKC", text).replace("\x00", "")
        patterns = (
            (r"\bsk-[a-zA-Z0-9_-]{20,}\b", "[REDACTED_OPENAI_SECRET]"),
            (r"\b(?:ghp|github_pat)_[a-zA-Z0-9_]{20,}\b", "[REDACTED_GITHUB_TOKEN]"),
            (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED_AWS_ACCESS_KEY]"),
            (r"\bxox[baprs]-[a-zA-Z0-9-]{10,}\b", "[REDACTED_SLACK_TOKEN]"),
            (
                r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
                r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                "[REDACTED_PRIVATE_KEY]",
            ),
            (r"(?i)\bBearer\s+[a-z0-9._~+/-]{20,}=*", "Bearer [REDACTED_TOKEN]"),
        )
        redactions = 0
        for pattern, replacement in patterns:
            text, count = re.subn(pattern, replacement, text, flags=re.DOTALL)
            redactions += count
        lines = [re.sub(r"[ \t]+$", "", line) for line in text.splitlines()]
        text = "\n".join(lines)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip(), redactions

    def parse_file(self, file_path: Path | str) -> ParsedDocument:
        """Parse one local document and enforce extraction quality gates."""
        path = Path(file_path).expanduser()
        if not path.exists() or not path.is_file():
            raise IngestionError(f"Document not found: {path}", code="file_not_found")
        size = path.stat().st_size
        if size <= 0:
            raise IngestionQualityError(f"Document is empty: {path}", code="empty_file")
        if size > self.max_bytes:
            raise IngestionError(
                f"Document exceeds {self.max_bytes} byte limit: {path}",
                code="file_too_large",
            )
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise UnsupportedFormatError(
                f"Unsupported document format {suffix or '<none>'}: {path}",
                code="unsupported_format",
            )

        raw = path.read_bytes()
        source_hash = _sha256_bytes(raw)
        self._validate_signature(path, raw)

        if suffix in TEXT_SUFFIXES:
            parsed = self._parse_text(path, raw, source_hash)
        elif suffix == ".csv":
            parsed = self._parse_csv(path, raw, source_hash)
        elif suffix == ".json":
            parsed = self._parse_json(path, raw, source_hash)
        elif suffix in HTML_SUFFIXES:
            parsed = self._parse_html(path, raw, source_hash)
        elif suffix in DOCLING_SUFFIXES:
            parsed = self._parse_layout_document(path, source_hash)
        else:  # pragma: no cover - the suffix set above is exhaustive
            raise UnsupportedFormatError(f"Unsupported document: {path}")

        normalized_text, _ = self._normalize_and_redact(parsed.text)
        normalized_tables = tuple(self._normalize_table(table) for table in parsed.tables)
        parsed = replace(parsed, text=normalized_text, tables=normalized_tables)
        return self._quality_gate(parsed)

    def _validate_signature(self, path: Path, raw: bytes) -> None:
        suffix = path.suffix.lower()
        if suffix == ".pdf" and not raw.startswith(b"%PDF-"):
            raise IngestionQualityError(
                f"File extension is PDF but signature is invalid: {path}",
                code="invalid_pdf_signature",
            )
        if suffix == ".docx" and not raw.startswith(b"PK"):
            raise IngestionQualityError(
                f"File extension is DOCX but ZIP signature is invalid: {path}",
                code="invalid_docx_signature",
            )

    def _decode_text(self, raw: bytes) -> tuple[str, tuple[str, ...]]:
        try:
            return raw.decode("utf-8-sig"), ()
        except UnicodeDecodeError:
            return raw.decode("cp1252"), ("decoded_as_cp1252",)

    def _parse_text(self, path: Path, raw: bytes, source_hash: str) -> ParsedDocument:
        text, warnings = self._decode_text(raw)
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        return ParsedDocument(
            source_path=str(path.resolve()),
            source_sha256=source_hash,
            title=title,
            media_type="text/markdown" if path.suffix.lower() != ".txt" else "text/plain",
            parser="text",
            text=text,
            provenance=({"kind": "file", "path": str(path)},),
            metadata={"bytes": len(raw)},
            warnings=warnings,
        )

    def _parse_csv(self, path: Path, raw: bytes, source_hash: str) -> ParsedDocument:
        text, warnings = self._decode_text(raw)
        rows = [[_normalize_cell(cell) for cell in row] for row in csv.reader(text.splitlines())]
        rows = [row for row in rows if any(row)]
        if not rows:
            raise IngestionQualityError(f"CSV contains no rows: {path}", code="empty_extraction")
        width = max(len(row) for row in rows)
        headers = tuple((*rows[0], *(f"column_{i + 1}" for i in range(len(rows[0]), width))))
        data_rows = tuple(tuple((*row, *("" for _ in range(width - len(row))))) for row in rows[1:])
        table = ExtractedTable(path.stem, headers, data_rows, 0, provenance={"row": 1})
        return ParsedDocument(
            source_path=str(path.resolve()),
            source_sha256=source_hash,
            title=path.stem,
            media_type="text/csv",
            parser="csv",
            text="",
            tables=(table,),
            provenance=({"kind": "rows", "start": 1, "end": len(rows)},),
            metadata={"row_count": len(data_rows), "column_count": width},
            warnings=warnings,
        )

    def _parse_json(self, path: Path, raw: bytes, source_hash: str) -> ParsedDocument:
        text, warnings = self._decode_text(raw)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IngestionQualityError(
                f"JSON is malformed: {path}: {exc}", code="malformed_json"
            ) from exc
        rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        return ParsedDocument(
            source_path=str(path.resolve()),
            source_sha256=source_hash,
            title=path.stem,
            media_type="application/json",
            parser="json",
            text=rendered,
            provenance=({"kind": "json", "path": "$"},),
            metadata={"root_type": type(value).__name__},
            warnings=warnings,
        )

    def _parse_html(self, path: Path, raw: bytes, source_hash: str) -> ParsedDocument:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise IngestionError(
                "HTML parsing requires beautifulsoup4; install the document-ingestion extra",
                code="missing_html_backend",
            ) from exc

        html, warnings = self._decode_text(raw)
        soup = BeautifulSoup(html, "html.parser")
        for node in soup.select(
            "script,style,noscript,template,svg,canvas,form,nav,footer,header,aside"
        ):
            node.decompose()
        root = soup.find("main") or soup.find("article") or soup.body or soup
        title_node = soup.find("title") or root.find(["h1", "h2"])
        title = title_node.get_text(" ", strip=True) if title_node else path.stem

        tables: list[ExtractedTable] = []
        for table_index, node in enumerate(root.find_all("table")):
            matrix: list[list[str]] = []
            header_row = False
            for row_index, row in enumerate(node.find_all("tr")):
                cells = row.find_all(["th", "td"])
                values = [_normalize_cell(cell.get_text(" ", strip=True)) for cell in cells]
                if values:
                    matrix.append(values)
                    header_row = header_row or (
                        row_index == 0 and any(c.name == "th" for c in cells)
                    )
            if matrix:
                width = max(len(row) for row in matrix)
                if header_row:
                    headers = tuple(
                        (*matrix[0], *(f"column_{i + 1}" for i in range(len(matrix[0]), width)))
                    )
                    body = matrix[1:]
                else:
                    headers = tuple(f"column_{i + 1}" for i in range(width))
                    body = matrix
                rows = tuple(tuple((*row, *("" for _ in range(width - len(row))))) for row in body)
                caption = node.find("caption")
                tables.append(
                    ExtractedTable(
                        title=(
                            caption.get_text(" ", strip=True)
                            if caption
                            else f"Table {table_index + 1}"
                        ),
                        headers=headers,
                        rows=rows,
                        table_index=table_index,
                        provenance={"selector": f"table:nth-of-type({table_index + 1})"},
                    )
                )
            node.decompose()

        blocks: list[str] = []
        provenance: list[dict[str, Any]] = []
        supported = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote"]
        for index, node in enumerate(root.find_all(supported)):
            if node.find_parent(["p", "li", "pre", "blockquote"]):
                continue
            value = node.get_text(" ", strip=True)
            if not value:
                continue
            if node.name and node.name.startswith("h"):
                value = f"{'#' * int(node.name[1])} {value}"
            elif node.name == "li":
                value = f"- {value}"
            elif node.name == "blockquote":
                value = f"> {value}"
            elif node.name == "pre":
                value = f"```\n{node.get_text(chr(10), strip=True)}\n```"
            blocks.append(value)
            provenance.append({"kind": "html", "tag": node.name, "ordinal": index})
        if not blocks:
            fallback = root.get_text("\n", strip=True)
            if fallback:
                blocks.append(fallback)
                provenance.append({"kind": "html", "selector": "body"})

        return ParsedDocument(
            source_path=str(path.resolve()),
            source_sha256=source_hash,
            title=title,
            media_type="text/html",
            parser="beautifulsoup4",
            text="\n\n".join(blocks),
            tables=tuple(tables),
            provenance=tuple(provenance),
            metadata={"table_count": len(tables), "element_count": len(blocks)},
            warnings=warnings,
        )

    def _parse_layout_document(self, path: Path, source_hash: str) -> ParsedDocument:
        if self.prefer_docling and self.capabilities()["backends"]["docling"]:
            try:
                return self._parse_with_docling(path, source_hash)
            except Exception as exc:
                if path.suffix.lower() != ".pdf":
                    if isinstance(exc, IngestionError):
                        raise
                    raise IngestionError(
                        f"Docling failed to parse {path}: {exc}", code="docling_failure"
                    ) from exc
                logger.warning("Docling failed for %s; trying PyMuPDF: %s", path, exc)
                parsed = self._parse_pdf_with_pymupdf(path, source_hash)
                return replace(parsed, warnings=(*parsed.warnings, "docling_failed_used_pymupdf"))
        if path.suffix.lower() == ".pdf":
            return self._parse_pdf_with_pymupdf(path, source_hash)
        raise IngestionError(
            f"{path.suffix} ingestion requires Docling; install the document-ingestion extra",
            code="missing_docling_backend",
        )

    def _get_docling_converter(self) -> Any:
        if self._docling_converter is not None:
            return self._docling_converter
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:  # pragma: no cover - guarded by capabilities
            raise IngestionError("Docling is unavailable", code="missing_docling_backend") from exc

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        if hasattr(options, "table_structure_options"):
            options.table_structure_options.do_cell_matching = True
        allowed = [
            fmt
            for name in ("PDF", "IMAGE", "DOCX", "HTML")
            if (fmt := getattr(InputFormat, name, None)) is not None
        ]
        self._docling_converter = DocumentConverter(
            allowed_formats=allowed,
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
        )
        return self._docling_converter

    def _parse_with_docling(self, path: Path, source_hash: str) -> ParsedDocument:
        converter = self._get_docling_converter()
        result = converter.convert(str(path))
        document = result.document
        text = document.export_to_markdown()

        tables: list[ExtractedTable] = []
        for table_index, item in enumerate(getattr(document, "tables", ())):
            try:
                dataframe = item.export_to_dataframe(doc=document)
                headers = tuple(_normalize_cell(value) for value in dataframe.columns)
                rows = tuple(
                    tuple(_normalize_cell(value) for value in row)
                    for row in dataframe.itertuples(index=False, name=None)
                )
            except Exception as exc:
                logger.warning("Docling table %s export failed: %s", table_index, exc)
                continue
            prov = self._docling_provenance(item)
            tables.append(
                ExtractedTable(
                    title=f"Table {table_index + 1}",
                    headers=headers,
                    rows=rows,
                    table_index=table_index,
                    page_number=prov.get("page_number"),
                    provenance=prov,
                )
            )

        provenance: list[dict[str, Any]] = []
        try:
            for index, (item, level) in enumerate(document.iterate_items()):
                if index >= 10_000:
                    break
                prov = self._docling_provenance(item)
                prov.update(
                    {
                        "kind": item.__class__.__name__,
                        "level": level,
                        "ordinal": index,
                    }
                )
                provenance.append(prov)
        except Exception as exc:
            logger.warning("Docling provenance extraction failed for %s: %s", path, exc)

        pages = getattr(document, "pages", {})
        metadata = {
            "page_count": len(pages) if hasattr(pages, "__len__") else None,
            "table_count": len(tables),
            "element_count": len(provenance),
        }
        try:
            from importlib.metadata import version

            metadata["docling_version"] = version("docling")
        except Exception as exc:  # pragma: no cover - metadata is best effort
            logger.debug("Docling version metadata unavailable: %s", exc)
        title = getattr(document, "name", None) or path.stem
        return ParsedDocument(
            source_path=str(path.resolve()),
            source_sha256=source_hash,
            title=str(title),
            media_type=self._media_type(path.suffix.lower()),
            parser="docling",
            text=text,
            tables=tuple(tables),
            provenance=tuple(provenance),
            metadata=metadata,
            ocr_enabled=path.suffix.lower() in {".pdf", *IMAGE_SUFFIXES},
        )

    def _docling_provenance(self, item: Any) -> dict[str, Any]:
        prov_items = getattr(item, "prov", None) or ()
        if not prov_items:
            return {}
        first = prov_items[0]
        result: dict[str, Any] = {}
        page_no = getattr(first, "page_no", None)
        if page_no is not None:
            result["page_number"] = int(page_no)
        bbox = getattr(first, "bbox", None)
        if bbox is not None:
            coords = {
                key: getattr(bbox, key)
                for key in ("l", "t", "r", "b")
                if getattr(bbox, key, None) is not None
            }
            if coords:
                result["bbox"] = coords
        return result

    def _parse_pdf_with_pymupdf(self, path: Path, source_hash: str) -> ParsedDocument:
        try:
            import fitz
        except ImportError as exc:
            raise IngestionError(
                "PDF parsing requires Docling or PyMuPDF; install the document-ingestion extra",
                code="missing_pdf_backend",
            ) from exc
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise IngestionQualityError(
                f"PDF is corrupt or unreadable: {path}: {exc}", code="corrupt_pdf"
            ) from exc
        try:
            if document.needs_pass:
                raise IngestionQualityError(
                    f"Encrypted PDF requires a password: {path}", code="encrypted_pdf"
                )
            page_texts: list[str] = []
            provenance: list[dict[str, Any]] = []
            tables: list[ExtractedTable] = []
            for page_index, page in enumerate(document):
                page_texts.append(page.get_text("text", sort=True).strip())
                provenance.append(
                    {
                        "kind": "page",
                        "page_number": page_index + 1,
                        "bbox": {
                            "l": page.rect.x0,
                            "t": page.rect.y0,
                            "r": page.rect.x1,
                            "b": page.rect.y1,
                        },
                    }
                )
                try:
                    found = page.find_tables()
                    for table in found.tables:
                        matrix = table.extract()
                        normalized = [
                            [_normalize_cell(cell) for cell in row] for row in matrix if row
                        ]
                        if not normalized:
                            continue
                        width = max(len(row) for row in normalized)
                        headers = tuple(
                            (
                                *normalized[0],
                                *(f"column_{i + 1}" for i in range(len(normalized[0]), width)),
                            )
                        )
                        rows = tuple(
                            tuple((*row, *("" for _ in range(width - len(row)))))
                            for row in normalized[1:]
                        )
                        tables.append(
                            ExtractedTable(
                                title=f"Table {len(tables) + 1}",
                                headers=headers,
                                rows=rows,
                                table_index=len(tables),
                                page_number=page_index + 1,
                                provenance={"page_number": page_index + 1},
                            )
                        )
                except Exception as exc:
                    logger.debug(
                        "PyMuPDF table extraction failed on page %s: %s", page_index + 1, exc
                    )
            page_texts = self._remove_repeated_page_margins(page_texts)
            full_text = "\n\n".join(text for text in page_texts if text)
            if len(re.sub(r"\s+", "", full_text)) < self.min_text_chars:
                raise IngestionQualityError(
                    "PDF has too little embedded text and requires the Docling OCR backend",
                    code="ocr_required",
                )
            return ParsedDocument(
                source_path=str(path.resolve()),
                source_sha256=source_hash,
                title=path.stem,
                media_type="application/pdf",
                parser="pymupdf",
                text=full_text,
                tables=tuple(tables),
                provenance=tuple(provenance),
                metadata={"page_count": len(page_texts), "table_count": len(tables)},
                warnings=("ocr_not_available_in_fallback",),
                ocr_enabled=False,
            )
        finally:
            document.close()

    def _remove_repeated_page_margins(self, pages: list[str]) -> list[str]:
        if len(pages) < 3:
            return pages
        candidates: dict[str, int] = {}
        split_pages = [page.splitlines() for page in pages]
        for lines in split_pages:
            for line in [*lines[:2], *lines[-2:]]:
                key = re.sub(r"\d+", "#", re.sub(r"\s+", " ", line)).strip()
                if len(key) >= 4:
                    candidates[key] = candidates.get(key, 0) + 1
        threshold = max(2, int(len(pages) * 0.6 + 0.999))
        repeated = {line for line, count in candidates.items() if count >= threshold}
        cleaned: list[str] = []
        for lines in split_pages:
            kept = []
            for line in lines:
                key = re.sub(r"\d+", "#", re.sub(r"\s+", " ", line)).strip()
                if key not in repeated:
                    kept.append(line)
            cleaned.append("\n".join(kept).strip())
        return cleaned

    def _media_type(self, suffix: str) -> str:
        return {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
        }.get(suffix, "application/octet-stream")

    def _normalize_table(self, table: ExtractedTable) -> ExtractedTable:
        width = table.width

        def normalize_value(value: object) -> str:
            normalized, _ = self._normalize_and_redact(_normalize_cell(value))
            return normalized

        headers = tuple(normalize_value(value) for value in table.headers)
        if width and not headers:
            headers = tuple(f"column_{i + 1}" for i in range(width))
        if len(headers) < width:
            headers = (*headers, *(f"column_{i + 1}" for i in range(len(headers), width)))
        rows = tuple(
            tuple(
                (*(normalize_value(value) for value in row), *("" for _ in range(width - len(row))))
            )
            for row in table.rows
        )
        title, _ = self._normalize_and_redact(table.title)
        return replace(table, title=title, headers=headers, rows=rows)

    def _quality_gate(self, parsed: ParsedDocument) -> ParsedDocument:
        text_chars = len(re.sub(r"[\s#>*_`|:-]+", "", parsed.text))
        table_chars = sum(
            len("".join(table.headers)) + sum(len("".join(row)) for row in table.rows)
            for table in parsed.tables
        )
        total_chars = text_chars + table_chars
        has_structured_table = any(
            len(table.headers) >= 2 and table.rows for table in parsed.tables
        )
        if total_chars < self.min_text_chars and not has_structured_table:
            raise IngestionQualityError(
                f"Extraction produced only {total_chars} useful characters from {parsed.source_path}",
                code="empty_extraction",
            )
        replacement_ratio = parsed.text.count("�") / max(1, len(parsed.text))
        if replacement_ratio > 0.02:
            raise IngestionQualityError(
                f"Extraction has excessive decode replacement characters: {replacement_ratio:.2%}",
                code="decode_corruption",
            )
        injection_signals = [
            name
            for name, pattern in PROMPT_INJECTION_PATTERNS.items()
            if pattern.search(parsed.text)
        ]
        score = 1.0
        if total_chars < self.min_text_chars:
            score -= 0.05
        if not parsed.provenance:
            score -= 0.15
        if parsed.parser == "pymupdf":
            score -= 0.10
        score -= min(0.25, 0.03 * len(parsed.warnings))
        warnings = parsed.warnings
        if injection_signals:
            score -= 0.10
            warnings = (*warnings, "prompt_injection_signals_detected")
        metadata = {
            **parsed.metadata,
            "useful_char_count": total_chars,
            "text_char_count": text_chars,
            "table_char_count": table_chars,
            "quality_gate": "passed",
            "content_trust": "untrusted_document_data",
            "prompt_injection_signals": injection_signals,
        }
        return replace(
            parsed,
            quality_score=max(0.0, round(score, 3)),
            metadata=metadata,
            warnings=warnings,
        )

    def chunk_document(
        self,
        parsed: ParsedDocument,
        *,
        chunk_size: int = 1_200,
        overlap: int = 120,
    ) -> tuple[DocumentChunk, ...]:
        """Create semantic chunks; every loop has a strict forward-progress invariant."""
        if chunk_size < 128:
            raise ValueError("chunk_size must be at least 128 characters")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

        body = parsed.text
        for table in parsed.tables:
            rendered = table.to_markdown()
            if rendered:
                body = body.replace(rendered, "")
        blocks = [block.strip() for block in re.split(r"\n{2,}", body) if block.strip()]
        raw_chunks: list[tuple[str, str, int | None, int | None, dict[str, Any]]] = []
        current = ""
        for block in blocks:
            candidate = f"{current}\n\n{block}".strip() if current else block
            if len(candidate) <= chunk_size:
                current = candidate
                continue
            if current:
                raw_chunks.append((current, "text", None, None, {}))
                current = ""
            if len(block) <= chunk_size:
                current = block
                continue
            start = 0
            while start < len(block):
                end = min(start + chunk_size, len(block))
                if end < len(block):
                    boundary = max(block.rfind(". ", start, end), block.rfind("\n", start, end))
                    if boundary > start + chunk_size // 2:
                        end = boundary + 1
                raw_chunks.append((block[start:end].strip(), "text", None, None, {}))
                if end >= len(block):
                    break
                start = max(start + 1, end - overlap)
        if current:
            raw_chunks.append((current, "text", None, None, {}))

        for table in parsed.tables:
            table_chunks = self._chunk_table(table, chunk_size)
            for text in table_chunks:
                raw_chunks.append(
                    (
                        text,
                        "table",
                        table.page_number,
                        table.page_number,
                        {"table_index": table.table_index, "table_title": table.title},
                    )
                )

        chunks: list[DocumentChunk] = []
        for index, (text, chunk_type, page_start, page_end, metadata) in enumerate(raw_chunks):
            if not text:
                continue
            chunk_hash = hashlib.sha256(
                f"{parsed.source_sha256}:{index}:{chunk_type}:{text}".encode()
            ).hexdigest()[:20]
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_hash,
                    text=text,
                    chunk_index=index,
                    chunk_type=chunk_type,
                    source_path=parsed.source_path,
                    source_sha256=parsed.source_sha256,
                    parser=parsed.parser,
                    page_start=page_start,
                    page_end=page_end,
                    metadata=metadata,
                )
            )
        if not chunks:
            raise IngestionQualityError(
                f"No retrieval chunks produced for {parsed.source_path}", code="empty_chunks"
            )
        return tuple(chunks)

    def _chunk_table(self, table: ExtractedTable, chunk_size: int) -> list[str]:
        header = ExtractedTable(
            title=table.title,
            headers=table.headers,
            rows=(),
            table_index=table.table_index,
        ).to_markdown()
        chunks: list[str] = []
        current_rows: list[tuple[str, ...]] = []
        for row in table.rows:
            candidate = ExtractedTable(
                table.title, table.headers, tuple((*current_rows, row)), table.table_index
            ).to_markdown()
            if current_rows and len(candidate) > chunk_size:
                chunks.append(
                    ExtractedTable(
                        table.title, table.headers, tuple(current_rows), table.table_index
                    ).to_markdown()
                )
                current_rows = [row]
            else:
                current_rows.append(row)
        if current_rows:
            chunks.append(
                ExtractedTable(
                    table.title, table.headers, tuple(current_rows), table.table_index
                ).to_markdown()
            )
        elif header:
            chunks.append(header)
        return chunks

    def ingest_file(
        self,
        file_path: Path | str,
        *,
        chunk_size: int = 1_200,
        overlap: int = 120,
    ) -> IngestedDocument:
        parsed = self.parse_file(file_path)
        chunks = self.chunk_document(parsed, chunk_size=chunk_size, overlap=overlap)
        table_text = "\n\n".join(
            table.to_markdown() for table in parsed.tables if table.to_markdown()
        )
        content = "\n\n".join(part for part in (parsed.text, table_text) if part).strip()
        metadata = {
            **parsed.metadata,
            "title": parsed.title,
            "source_sha256": parsed.source_sha256,
            "parser": parsed.parser,
            "media_type": parsed.media_type,
            "quality_score": parsed.quality_score,
            "ocr_enabled": parsed.ocr_enabled,
            "warnings": list(parsed.warnings),
            "table_count": len(parsed.tables),
            "chunk_count": len(chunks),
            "provenance_count": len(parsed.provenance),
        }
        return self._register_document(
            Path(file_path),
            content,
            metadata=metadata,
            parser=parsed.parser,
            media_type=parsed.media_type,
            quality_score=parsed.quality_score,
            chunks=chunks,
            tables=parsed.tables,
        )

    def ingest_document(self, file_path: Path, raw_content: str) -> IngestedDocument:
        """Compatibility entrypoint for trusted callers that already extracted text."""
        return self._register_document(
            file_path,
            raw_content,
            metadata={},
            parser="raw-text",
            media_type="text/plain",
            quality_score=1.0,
            chunks=(),
            tables=(),
        )

    def _register_document(
        self,
        file_path: Path,
        raw_content: str,
        *,
        metadata: dict[str, Any],
        parser: str,
        media_type: str,
        quality_score: float,
        chunks: tuple[DocumentChunk, ...],
        tables: tuple[ExtractedTable, ...],
    ) -> IngestedDocument:
        normalized, redaction_count = self._normalize_and_redact(raw_content)
        if not normalized:
            raise IngestionQualityError("Cannot register empty content", code="empty_content")
        content_hash = self.compute_sha256(normalized)
        match = re.search(r"LL-\d+", file_path.name, re.IGNORECASE)
        lesson_id = match.group(0).upper() if match else file_path.stem
        source_key = self._source_key(file_path, lesson_id)
        now = _utc_now()

        with self._manifest_lock():
            manifest = self._load_manifest()
            existing = manifest["documents"].get(source_key, {})
            duplicate_of = manifest["hash_index"].get(content_hash)
            same_source_duplicate = existing.get("sha256_hash") == content_hash
            is_duplicate = same_source_duplicate or duplicate_of is not None
            version = (
                int(existing.get("version", 0))
                if same_source_duplicate
                else int(existing.get("version", 0)) + 1
            )
            if duplicate_of == source_key:
                duplicate_of = None

            final_metadata = {
                **metadata,
                "file_name": file_path.name,
                "char_count": len(normalized),
                "line_count": len(normalized.splitlines()),
                "redaction_count": redaction_count,
                "source_key": source_key,
            }
            history = list(existing.get("history", []))
            if existing and not same_source_duplicate:
                history.append(
                    {
                        "version": int(existing.get("version", 0)),
                        "sha256_hash": existing.get("sha256_hash"),
                        "parser": existing.get("parser"),
                        "quality_score": existing.get("quality_score"),
                        "last_ingested_at": existing.get("last_ingested_at"),
                    }
                )
            record = {
                "lesson_id": lesson_id,
                "sha256_hash": content_hash,
                "version": version,
                "file_path": str(file_path),
                "parser": parser,
                "media_type": media_type,
                "quality_score": quality_score,
                "duplicate_of": duplicate_of,
                "first_ingested_at": existing.get("first_ingested_at", now),
                "last_ingested_at": now,
                "history": history,
                "metadata": final_metadata,
            }
            if not same_source_duplicate:
                manifest["documents"][source_key] = record
                manifest["hash_index"].setdefault(content_hash, source_key)
                manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
                manifest["total_ingested"] = len(manifest["documents"])
                manifest["total_unique"] = len(manifest["hash_index"])
                manifest["last_updated"] = now
                self._save_manifest_unlocked(manifest)
            self.manifest = manifest

        return IngestedDocument(
            lesson_id=lesson_id,
            file_path=str(file_path),
            sha256_hash=content_hash,
            version=version,
            normalized_content=normalized,
            metadata=final_metadata,
            is_duplicate=is_duplicate,
            duplicate_of=duplicate_of,
            parser=parser,
            media_type=media_type,
            quality_score=quality_score,
            chunks=chunks,
            tables=tables,
        )

    def _source_key(self, file_path: Path, lesson_id: str) -> str:
        if lesson_id.upper().startswith("LL-"):
            return lesson_id.upper()
        try:
            return str(file_path.resolve())
        except OSError:
            return str(file_path)

    @contextmanager
    def _manifest_lock(self) -> Iterator[None]:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.manifest_path.with_suffix(self.manifest_path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            try:
                import fcntl

                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            except ImportError:  # pragma: no cover - production is macOS/Linux
                pass
            try:
                yield
            finally:
                try:
                    import fcntl

                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                except ImportError:  # pragma: no cover
                    pass

    def save_manifest(self) -> None:
        with self._manifest_lock():
            self._save_manifest_unlocked(self.manifest)

    def _save_manifest_unlocked(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.manifest_path.name}.",
            suffix=".tmp",
            dir=self.manifest_path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.manifest_path)
        except Exception:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def parsed_to_dict(parsed: ParsedDocument) -> dict[str, Any]:
        return asdict(parsed)

    @staticmethod
    def ingested_to_dict(
        document: IngestedDocument, *, include_content: bool = False
    ) -> dict[str, Any]:
        payload = asdict(document)
        if not include_content:
            payload.pop("normalized_content", None)
            for chunk in payload.get("chunks", []):
                chunk.pop("text", None)
        return payload
