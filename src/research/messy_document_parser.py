"""World-class multi-format document extraction for messy financial docs.

Production cascade for PDF / HTML / plain text / images (OCR gate):

1. **Docling** (optional) — layout-aware PDF/DOCX/images when installed
2. **pdfplumber** (optional) — better digital PDF text + tables
3. **pypdf** (optional, preferred lightweight) — page text extract
4. **HTML cleaner** (stdlib) — strip scripts/styles/nav chrome
5. **Plain text / Markdown** — passthrough with light cleanup
6. **Quality gate** — reject empty / garbage / likely-scanned without OCR

Design rules (trading desk, not demo theater):
- Never silently index empty extraction
- Always report which backend produced the text
- Tables preserved as Markdown when extractable
- OCR is an explicit fail/flag until a backend is installed (no fake success)

Optional installs::

    pip install '.[documents]'          # pypdf + pdfplumber + beautifulsoup4
    pip install docling                 # heavy layout parser (optional)

This module does **not** claim trading edge. It only raises document fidelity.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quality thresholds (fail closed for RAG safety)
# ---------------------------------------------------------------------------
MIN_CHARS_DEFAULT = 40
MIN_ALNUM_RATIO = 0.25
MIN_CHARS_PER_PDF_PAGE = 15  # below → likely scanned / empty extract
MAX_REPEATED_CHAR_RATIO = 0.45


@dataclass
class ExtractedTable:
    """Table extracted during parse."""

    title: str
    headers: list[str]
    rows: list[list[str]]
    page_number: int = 0
    source: str = "unknown"

    def to_markdown(self) -> str:
        if not self.headers and not self.rows:
            return ""
        headers = self.headers or [f"col_{i}" for i in range(len(self.rows[0]))]
        lines = []
        if self.title:
            lines.append(f"**{self.title}**")
            lines.append("")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in self.rows:
            padded = list(row) + [""] * max(0, len(headers) - len(row))
            lines.append("| " + " | ".join(str(c) for c in padded[: len(headers)]) + " |")
        return "\n".join(lines)


@dataclass
class ParseQuality:
    """Extraction quality metrics and gate result."""

    char_count: int = 0
    page_count: int = 0
    table_count: int = 0
    alnum_ratio: float = 0.0
    chars_per_page: float = 0.0
    likely_scanned: bool = False
    empty_extract: bool = False
    garbage: bool = False
    passed: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Normalized parse result ready for RAG ingestion."""

    source_path: str
    format: str  # pdf | html | markdown | text | image | unknown
    text: str
    markdown: str
    backend: str  # docling | pdfplumber | pypdf | html_stdlib | plaintext | none
    tables: list[ExtractedTable] = field(default_factory=list)
    quality: ParseQuality = field(default_factory=ParseQuality)
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "format": self.format,
            "backend": self.backend,
            "char_count": len(self.text),
            "table_count": len(self.tables),
            "content_hash": self.content_hash,
            "quality": asdict(self.quality),
            "metadata": self.metadata,
            "warnings": self.warnings,
            "text_preview": self.text[:500],
        }


class _HTMLTextExtractor(HTMLParser):
    """Stdlib HTML → visible text (no BeautifulSoup required)."""

    SKIP_TAGS = frozenset(
        {
            "script",
            "style",
            "noscript",
            "svg",
            "path",
            "nav",
            "footer",
            "header",
            "aside",
            "iframe",
            "form",
            "button",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_buf: list[str] = []
        self.tables: list[ExtractedTable] = []
        self._table_index = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if t in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append("\n")
        if t == "table":
            self._in_table = True
            self._table_rows = []
        elif t == "tr" and self._in_table:
            self._current_row = []
        elif t in ("td", "th") and self._in_table:
            self._cell_buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if t in ("td", "th") and self._in_table:
            self._current_row.append("".join(self._cell_buf).strip())
            self._cell_buf = []
        elif t == "tr" and self._in_table:
            if any(c.strip() for c in self._current_row):
                self._table_rows.append(self._current_row)
            self._current_row = []
        elif t == "table" and self._in_table:
            self._in_table = False
            if self._table_rows:
                headers = self._table_rows[0]
                rows = self._table_rows[1:] if len(self._table_rows) > 1 else []
                self._table_index += 1
                self.tables.append(
                    ExtractedTable(
                        title=f"HTML Table {self._table_index}",
                        headers=headers,
                        rows=rows,
                        source="html_stdlib",
                    )
                )
            self._table_rows = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_table and self._cell_buf is not None:
            # still capture into cell buffer when inside td/th
            pass
        text = data.strip()
        if not text:
            return
        if self._in_table:
            self._cell_buf.append(data)
        self._chunks.append(data)

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"[ \t]{2,}", " ", raw)
        return raw.strip()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _alnum_ratio(text: str) -> float:
    if not text:
        return 0.0
    alnum = sum(1 for c in text if c.isalnum())
    return alnum / max(len(text), 1)


def _repeated_char_ratio(text: str) -> float:
    if len(text) < 20:
        return 0.0
    # crude garbage detector: long runs of same char
    runs = re.findall(r"(.)\1{8,}", text)
    if not runs:
        return 0.0
    bad = sum(len(m.group(0)) for m in re.finditer(r"(.)\1{8,}", text))
    return bad / len(text)


def assess_quality(
    text: str,
    *,
    page_count: int = 0,
    table_count: int = 0,
    min_chars: int = MIN_CHARS_DEFAULT,
    format_hint: str = "",
) -> ParseQuality:
    """Fail-closed quality gate for extracted text."""
    q = ParseQuality(
        char_count=len(text or ""),
        page_count=page_count,
        table_count=table_count,
        alnum_ratio=_alnum_ratio(text or ""),
        chars_per_page=(len(text or "") / page_count) if page_count else float(len(text or "")),
    )
    reasons: list[str] = []

    if not text or not text.strip():
        q.empty_extract = True
        reasons.append("empty_extract")
    elif len(text.strip()) < min_chars:
        q.empty_extract = True
        reasons.append(f"below_min_chars:{min_chars}")

    if q.alnum_ratio < MIN_ALNUM_RATIO and q.char_count >= min_chars:
        q.garbage = True
        reasons.append(f"low_alnum_ratio:{q.alnum_ratio:.2f}")

    if _repeated_char_ratio(text or "") > MAX_REPEATED_CHAR_RATIO:
        q.garbage = True
        reasons.append("high_repeated_char_ratio")

    if format_hint == "pdf" and page_count > 0:
        if q.chars_per_page < MIN_CHARS_PER_PDF_PAGE:
            q.likely_scanned = True
            reasons.append(
                f"likely_scanned:chars_per_page={q.chars_per_page:.1f}<{MIN_CHARS_PER_PDF_PAGE}"
            )

    q.reasons = reasons
    # Pass only if we have real text and not garbage; scanned still fails (needs OCR)
    q.passed = (not q.empty_extract) and (not q.garbage) and (not q.likely_scanned)
    return q


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\x00", "")
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines).strip()


def _tables_to_markdown_appendix(tables: list[ExtractedTable]) -> str:
    if not tables:
        return ""
    parts = ["", "## Extracted Tables", ""]
    for t in tables:
        md = t.to_markdown()
        if md:
            parts.append(md)
            parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Backend probes
# ---------------------------------------------------------------------------


def available_backends() -> dict[str, bool]:
    """Report which extractors are importable in this environment."""
    out = {
        "docling": False,
        "pdfplumber": False,
        "pypdf": False,
        "bs4": False,
        "html_stdlib": True,
        "plaintext": True,
    }
    try:
        import docling  # noqa: F401

        out["docling"] = True
    except ImportError:
        pass
    try:
        import pdfplumber  # noqa: F401

        out["pdfplumber"] = True
    except ImportError:
        pass
    try:
        import pypdf  # noqa: F401

        out["pypdf"] = True
    except ImportError:
        try:
            import PyPDF2  # noqa: F401

            out["pypdf"] = True  # legacy name still usable via adapter
        except ImportError:
            pass
    try:
        import bs4  # noqa: F401

        out["bs4"] = True
    except ImportError:
        pass
    return out


def _extract_pdf_docling(path: Path) -> tuple[str, list[ExtractedTable], dict[str, Any]] | None:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        return None
    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        document = result.document
        text = document.export_to_markdown()
        tables: list[ExtractedTable] = []
        # Best-effort table walk (Docling API varies by version)
        body = getattr(document, "body", None) or []
        idx = 0
        for item in body:
            label = str(getattr(item, "label", "")).lower()
            if "table" not in label:
                continue
            data = getattr(item, "table_data", None) or getattr(item, "data", None)
            if not data:
                continue
            try:
                rows_raw = list(data)
                headers = [str(h) for h in (rows_raw[0] if rows_raw else [])]
                rows = [[str(c) for c in r] for r in rows_raw[1:]]
                idx += 1
                tables.append(
                    ExtractedTable(
                        title=f"Table {idx}",
                        headers=headers,
                        rows=rows,
                        page_number=int(getattr(item, "page_no", 0) or 0),
                        source="docling",
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("Docling table skip: %s", e)
        meta = {
            "pages": getattr(document, "num_pages", None),
            "backend_detail": "docling.DocumentConverter",
        }
        return text, tables, meta
    except Exception as e:  # noqa: BLE001
        logger.warning("Docling failed for %s: %s", path, e)
        return None


def _extract_pdf_pdfplumber(
    path: Path,
) -> tuple[str, list[ExtractedTable], dict[str, Any]] | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        pages_text: list[str] = []
        tables: list[ExtractedTable] = []
        t_idx = 0
        with pdfplumber.open(path) as pdf:
            for pi, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append(t)
                try:
                    for raw in page.extract_tables() or []:
                        if not raw:
                            continue
                        headers = [str(c or "") for c in raw[0]]
                        rows = [[str(c or "") for c in r] for r in raw[1:]]
                        t_idx += 1
                        tables.append(
                            ExtractedTable(
                                title=f"Table {t_idx}",
                                headers=headers,
                                rows=rows,
                                page_number=pi + 1,
                                source="pdfplumber",
                            )
                        )
                except Exception as e:  # noqa: BLE001
                    logger.debug("pdfplumber table page %s: %s", pi, e)
            page_count = len(pdf.pages)
        text = "\n\n".join(pages_text)
        return text, tables, {"pages": page_count, "backend_detail": "pdfplumber"}
    except Exception as e:  # noqa: BLE001
        logger.warning("pdfplumber failed for %s: %s", path, e)
        return None


def _extract_pdf_pypdf(path: Path) -> tuple[str, list[ExtractedTable], dict[str, Any]] | None:
    reader = None
    backend_detail = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        backend_detail = "pypdf.PdfReader"
    except ImportError:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            backend_detail = "PyPDF2.PdfReader"
        except ImportError:
            return None
    try:
        pages_text: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                pages_text.append(t)
        text = "\n\n".join(pages_text)
        return text, [], {"pages": len(reader.pages), "backend_detail": backend_detail}
    except Exception as e:  # noqa: BLE001
        logger.warning("pypdf failed for %s: %s", path, e)
        return None


def parse_pdf(path: Path) -> ParsedDocument:
    """Parse PDF with Docling → pdfplumber → pypdf cascade.

    Quality-gate failures (short/empty extract, garbage) must not short-circuit
    the cascade: a later backend may extract real text. Only return a failed
    quality result after all backends have been tried (or on true success).
    """
    warnings: list[str] = []
    attempts: list[str] = []
    best_failed: ParsedDocument | None = None

    for name, fn in (
        ("docling", _extract_pdf_docling),
        ("pdfplumber", _extract_pdf_pdfplumber),
        ("pypdf", _extract_pdf_pypdf),
    ):
        attempts.append(name)
        result = fn(path)
        if result is None:
            continue
        text, tables, meta = result
        text = _normalize_text(text)
        page_count = int(meta.get("pages") or 0)
        quality = assess_quality(
            text, page_count=page_count, table_count=len(tables), format_hint="pdf"
        )
        # Accept only a true quality pass mid-cascade. Previously we also
        # accepted any non-garbage/non-scanned text (including empty_extract
        # short strings), which blocked pdfplumber/pypdf fallbacks.
        if quality.passed:
            md = text + _tables_to_markdown_appendix(tables)
            return ParsedDocument(
                source_path=str(path),
                format="pdf",
                text=text,
                markdown=md,
                backend=name,
                tables=tables,
                quality=quality,
                metadata={**meta, "attempts": attempts},
                content_hash=_content_hash(text),
                warnings=list(warnings),
            )
        if text:
            warnings.append(f"{name}_quality_fail:{','.join(quality.reasons)}")
            md = text + _tables_to_markdown_appendix(tables)
            candidate = ParsedDocument(
                source_path=str(path),
                format="pdf",
                text=text,
                markdown=md,
                backend=name,
                tables=tables,
                quality=quality,
                metadata={**meta, "attempts": list(attempts)},
                content_hash=_content_hash(text),
                warnings=list(warnings),
            )
            if best_failed is None or len(text) > len(best_failed.text or ""):
                best_failed = candidate
        # continue to next backend — do not return on empty_extract/scanned yet

    if best_failed is not None:
        if best_failed.quality.likely_scanned and "REQUIRES_OCR" not in best_failed.warnings:
            best_failed.warnings = list(best_failed.warnings) + ["REQUIRES_OCR"]
        best_failed.metadata = {**best_failed.metadata, "attempts": attempts}
        return best_failed

    # Total failure
    quality = assess_quality("", page_count=0, format_hint="pdf")
    quality.reasons.append("no_pdf_backend_or_all_failed")
    return ParsedDocument(
        source_path=str(path),
        format="pdf",
        text="",
        markdown="",
        backend="none",
        tables=[],
        quality=quality,
        metadata={"attempts": attempts, "available": available_backends()},
        content_hash=_content_hash(""),
        warnings=["no_extractable_text", "install_documents_extra_or_docling"],
    )


def parse_html(path: Path | None = None, *, html: str | None = None) -> ParsedDocument:
    """Parse HTML file or string via stdlib cleaner (+ optional bs4)."""
    if html is None:
        if path is None:
            raise ValueError("parse_html requires path or html=")
        raw = path.read_text(encoding="utf-8", errors="replace")
        source = str(path)
    else:
        raw = html
        source = str(path) if path else "<string>"

    backend = "html_stdlib"
    tables: list[ExtractedTable] = []
    text = ""

    # Prefer bs4 if present for robustness
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw, "html.parser")
        # Match _HTMLTextExtractor.SKIP_TAGS so the recommended `.[documents]`
        # path does not ingest nav/chrome/footer as document body.
        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
                "path",
                "iframe",
                "nav",
                "footer",
                "header",
                "aside",
                "form",
                "button",
            ]
        ):
            tag.decompose()
        for ti, table in enumerate(soup.find_all("table"), start=1):
            rows_out: list[list[str]] = []
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if cells:
                    rows_out.append(cells)
            if rows_out:
                tables.append(
                    ExtractedTable(
                        title=f"HTML Table {ti}",
                        headers=rows_out[0],
                        rows=rows_out[1:],
                        source="bs4",
                    )
                )
        text = soup.get_text("\n")
        backend = "bs4"
    except ImportError:
        extractor = _HTMLTextExtractor()
        try:
            extractor.feed(raw)
            extractor.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("HTML parse error: %s", e)
        text = extractor.get_text()
        tables = extractor.tables

    text = _normalize_text(text)
    quality = assess_quality(text, table_count=len(tables), format_hint="html")
    md = text + _tables_to_markdown_appendix(tables)
    return ParsedDocument(
        source_path=source,
        format="html",
        text=text,
        markdown=md,
        backend=backend,
        tables=tables,
        quality=quality,
        metadata={},
        content_hash=_content_hash(text),
        warnings=[] if quality.passed else list(quality.reasons),
    )


def parse_text_file(path: Path) -> ParsedDocument:
    """Markdown / plain text passthrough with normalization."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = _normalize_text(raw)
    fmt = "markdown" if path.suffix.lower() in {".md", ".markdown"} else "text"
    quality = assess_quality(text, format_hint=fmt)
    return ParsedDocument(
        source_path=str(path),
        format=fmt,
        text=text,
        markdown=text,
        backend="plaintext",
        tables=[],
        quality=quality,
        metadata={},
        content_hash=_content_hash(text),
        warnings=[] if quality.passed else list(quality.reasons),
    )


def parse_image(path: Path) -> ParsedDocument:
    """Image path: no OCR backend wired — fail closed with REQUIRES_OCR."""
    quality = assess_quality("", format_hint="image")
    quality.likely_scanned = True
    quality.reasons.append("REQUIRES_OCR")
    return ParsedDocument(
        source_path=str(path),
        format="image",
        text="",
        markdown="",
        backend="none",
        tables=[],
        quality=quality,
        metadata={"hint": "install docling with OCR models or tesseract path"},
        content_hash=_content_hash(""),
        warnings=["REQUIRES_OCR", "image_ocr_not_configured"],
    )


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".html", ".htm", ".xhtml"}:
        return "html"
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext in {".txt", ".text", ".log"}:
        return "text"
    if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".gif"}:
        return "image"
    return "unknown"


def parse_document(
    path: str | Path,
    *,
    require_quality_pass: bool = False,
) -> ParsedDocument:
    """Unified entry: detect format and run the appropriate cascade.

    Args:
        path: Filesystem path to document
        require_quality_pass: If True, raise ValueError when quality gate fails
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    fmt = detect_format(filepath)
    if fmt == "pdf":
        doc = parse_pdf(filepath)
    elif fmt == "html":
        doc = parse_html(filepath)
    elif fmt in {"markdown", "text"}:
        doc = parse_text_file(filepath)
    elif fmt == "image":
        doc = parse_image(filepath)
    else:
        # Try UTF-8 text, else fail
        try:
            doc = parse_text_file(filepath)
            doc.format = "unknown"
            doc.warnings.append("unknown_extension_read_as_text")
        except Exception as e:  # noqa: BLE001
            quality = assess_quality("")
            quality.reasons.append(f"unreadable:{e}")
            doc = ParsedDocument(
                source_path=str(filepath),
                format="unknown",
                text="",
                markdown="",
                backend="none",
                quality=quality,
                warnings=[str(e)],
            )

    if require_quality_pass and not doc.quality.passed:
        raise ValueError(f"Document quality gate failed for {filepath}: {doc.quality.reasons}")
    return doc


def parse_to_rag_payload(
    path: str | Path,
    *,
    require_quality_pass: bool = True,
) -> dict[str, Any]:
    """Parse and return a dict ready for DocumentIngestionPipeline."""
    doc = parse_document(path, require_quality_pass=require_quality_pass)
    return {
        "text": doc.text,
        "markdown": doc.markdown,
        "backend": doc.backend,
        "format": doc.format,
        "tables": [asdict(t) for t in doc.tables],
        "quality": asdict(doc.quality),
        "content_hash": doc.content_hash,
        "metadata": doc.metadata,
        "warnings": doc.warnings,
        "source_path": doc.source_path,
    }


__all__ = [
    "ExtractedTable",
    "ParseQuality",
    "ParsedDocument",
    "assess_quality",
    "available_backends",
    "detect_format",
    "parse_document",
    "parse_html",
    "parse_image",
    "parse_pdf",
    "parse_text_file",
    "parse_to_rag_payload",
]
