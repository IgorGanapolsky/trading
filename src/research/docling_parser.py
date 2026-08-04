"""
IBM Docling Parser for Financial Documents.

Integrates IBM Docling for parsing SEC filings, earnings reports, and Fed minutes
with layout understanding. Converts documents to structured Markdown for RAG ingestion.

References:
- Docling: https://github.com/DS4SD/docling
- Document understanding for RAG: https://arxiv.org/abs/2406.15319

Created: February 2, 2026
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research"
PARSED_DIR = RESEARCH_DIR / "parsed_documents"

# Ensure directories exist
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
PARSED_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ParsedTable:
    """A table extracted from a document."""

    title: str
    headers: list[str]
    rows: list[list[str]]
    page_number: int
    table_index: int

    def to_dataframe(self) -> Any:
        """Convert to pandas DataFrame."""
        try:
            import pandas as pd

            return pd.DataFrame(self.rows, columns=self.headers)
        except ImportError:
            logger.warning("pandas not installed, returning dict instead")
            return {"headers": self.headers, "rows": self.rows}

    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        lines = []
        if self.title:
            lines.append(f"**{self.title}**\n")

        # Header row
        lines.append("| " + " | ".join(self.headers) + " |")
        # Separator
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        # Data rows
        for row in self.rows:
            # Pad row if needed
            padded = row + [""] * (len(self.headers) - len(row))
            lines.append("| " + " | ".join(padded[: len(self.headers)]) + " |")

        return "\n".join(lines)


@dataclass
class FinancialMetrics:
    """Key financial metrics extracted from a document."""

    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    ebitda: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cash_flow: Optional[float] = None
    guidance: Optional[str] = None
    fiscal_period: Optional[str] = None
    raw_metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "revenue": self.revenue,
            "net_income": self.net_income,
            "eps": self.eps,
            "ebitda": self.ebitda,
            "gross_margin": self.gross_margin,
            "operating_margin": self.operating_margin,
            "debt_to_equity": self.debt_to_equity,
            "free_cash_flow": self.free_cash_flow,
            "guidance": self.guidance,
            "fiscal_period": self.fiscal_period,
            "raw_metrics": self.raw_metrics,
        }


@dataclass
class ParsedSection:
    """A section from a parsed document."""

    title: str
    content: str
    level: int  # Heading level (1, 2, 3, etc.)
    page_start: int
    page_end: int
    tables: list[ParsedTable] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class DoclingDocument:
    """A fully parsed document from Docling."""

    source_path: str
    title: str
    document_type: str  # 'sec_filing', 'earnings_report', 'fed_minutes', 'other'
    content_hash: str
    full_text: str
    sections: list[ParsedSection]
    tables: list[ParsedTable]
    metadata: dict
    parsed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "title": self.title,
            "document_type": self.document_type,
            "content_hash": self.content_hash,
            "full_text": (
                self.full_text[:1000] + "..." if len(self.full_text) > 1000 else self.full_text
            ),
            "section_count": len(self.sections),
            "table_count": len(self.tables),
            "metadata": self.metadata,
            "parsed_at": self.parsed_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert entire document to structured Markdown."""
        lines = []

        # Document header
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"**Source**: {Path(self.source_path).name}")
        lines.append(f"**Type**: {self.document_type}")
        lines.append(f"**Parsed**: {self.parsed_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # Metadata section
        if self.metadata:
            lines.append("## Document Metadata")
            for key, value in self.metadata.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        # Sections
        for section in self.sections:
            heading = "#" * min(section.level + 1, 6)
            lines.append(f"{heading} {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

            # Include tables in section
            for table in section.tables:
                lines.append(table.to_markdown())
                lines.append("")

        # Standalone tables at the end
        if self.tables:
            standalone = [t for t in self.tables if not any(t in s.tables for s in self.sections)]
            if standalone:
                lines.append("## Tables")
                lines.append("")
                for table in standalone:
                    lines.append(table.to_markdown())
                    lines.append("")

        return "\n".join(lines)


class DoclingFinancialParser:
    """
    Parser for financial documents using IBM Docling.

    Capabilities:
    - Parse PDF, DOCX, and images with layout understanding
    - Preserve document structure (headings, tables, code blocks)
    - Extract tables as DataFrames
    - Extract key financial metrics
    - Convert to Markdown for RAG ingestion
    """

    # Document type detection patterns
    DOCUMENT_TYPE_PATTERNS = {
        "sec_filing": [
            r"form\s*10-[kq]",
            r"form\s*8-k",
            r"securities\s*and\s*exchange\s*commission",
            r"sec\s*filing",
            r"edgar",
        ],
        "earnings_report": [
            r"earnings\s*release",
            r"quarterly\s*results",
            r"financial\s*results",
            r"q[1-4]\s*\d{4}",
            r"fiscal\s*(year|quarter)",
        ],
        "fed_minutes": [
            r"federal\s*reserve",
            r"fomc\s*minutes",
            r"federal\s*open\s*market\s*committee",
            r"monetary\s*policy",
            r"board\s*of\s*governors",
        ],
    }

    # Financial metric patterns
    METRIC_PATTERNS = {
        "revenue": [
            r"(?:total\s*)?revenue[:\s]+\$?([\d,]+\.?\d*)\s*(million|billion|M|B)?",
            r"net\s*sales[:\s]+\$?([\d,]+\.?\d*)\s*(million|billion|M|B)?",
        ],
        "net_income": [
            r"net\s*income[:\s]+\$?([\d,]+\.?\d*)\s*(million|billion|M|B)?",
            r"net\s*(?:profit|earnings)[:\s]+\$?([\d,]+\.?\d*)\s*(million|billion|M|B)?",
        ],
        "eps": [
            r"(?:diluted\s*)?eps[:\s]+\$?([\d,]+\.?\d*)",
            r"earnings\s*per\s*share[:\s]+\$?([\d,]+\.?\d*)",
        ],
        "ebitda": [
            r"ebitda[:\s]+\$?([\d,]+\.?\d*)\s*(million|billion|M|B)?",
            r"adjusted\s*ebitda[:\s]+\$?([\d,]+\.?\d*)\s*(million|billion|M|B)?",
        ],
        "gross_margin": [
            r"gross\s*margin[:\s]+([\d,]+\.?\d*)\s*%?",
            r"gross\s*profit\s*margin[:\s]+([\d,]+\.?\d*)\s*%?",
        ],
        "operating_margin": [
            r"operating\s*margin[:\s]+([\d,]+\.?\d*)\s*%?",
            r"op(?:erating)?\s*margin[:\s]+([\d,]+\.?\d*)\s*%?",
        ],
    }

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or PARSED_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._docling_converter = None

    def _init_docling(self) -> bool:
        """Initialize Docling converter."""
        if self._docling_converter is not None:
            return True

        try:
            from docling.document_converter import DocumentConverter

            self._docling_converter = DocumentConverter()
            logger.info("Docling initialized successfully")
            return True
        except ImportError:
            logger.error("Docling not installed. Run: pip install docling>=2.70.0")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Docling: {e}")
            return False

    def _get_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:12]

    def _detect_document_type(self, text: str) -> str:
        """Detect document type from content."""
        text_lower = text.lower()

        for doc_type, patterns in self.DOCUMENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return doc_type

        return "other"

    def _extract_title(self, text: str, filepath: Path) -> str:
        """Extract document title from content or filename."""
        # Try to find title in first few lines
        lines = text.split("\n")[:20]
        for line in lines:
            line = line.strip()
            # Skip empty lines and very short lines
            if len(line) > 10 and len(line) < 200:
                # Check if it looks like a title (mostly alphanumeric, possibly with some punctuation)
                if re.match(r"^[A-Z].*[a-zA-Z0-9]$", line) and line.count(".") < 3:
                    return line

        # Fall back to filename
        return filepath.stem.replace("_", " ").replace("-", " ").title()

    def parse_pdf(self, path: str | Path) -> Optional[DoclingDocument]:
        """
        Parse a PDF document using Docling.

        Args:
            path: Path to the PDF file

        Returns:
            DoclingDocument with full structure and content
        """
        filepath = Path(path)
        if not filepath.exists():
            logger.error(f"File not found: {path}")
            return None

        if filepath.suffix.lower() != ".pdf":
            logger.warning(f"Expected PDF file, got: {filepath.suffix}")

        if not self._init_docling():
            # Fall back to basic PDF parsing
            return self._fallback_parse_pdf(filepath)

        try:
            # Use Docling for advanced parsing
            result = self._docling_converter.convert(str(filepath))
            document = result.document

            # Extract full text
            full_text = document.export_to_markdown()

            # Extract sections
            sections = self._extract_sections_from_docling(document)

            # Extract tables
            tables = self._extract_tables_from_docling(document)

            # Detect document type
            doc_type = self._detect_document_type(full_text)

            # Extract title
            title = self._extract_title(full_text, filepath)

            # Build metadata
            metadata = {
                "pages": document.num_pages if hasattr(document, "num_pages") else None,
                "source": "docling",
                "detected_type": doc_type,
            }

            return DoclingDocument(
                source_path=str(filepath),
                title=title,
                document_type=doc_type,
                content_hash=self._get_content_hash(full_text),
                full_text=full_text,
                sections=sections,
                tables=tables,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Docling parsing failed for {path}: {e}")
            return self._fallback_parse_pdf(filepath)

    def _fallback_parse_pdf(self, filepath: Path) -> Optional[DoclingDocument]:
        """Fallback PDF parsing via production cascade (pdfplumber → pypdf).

        Delegates to ``messy_document_parser`` so Docling and the unified
        multi-format path share one quality-gated backend stack.
        """
        try:
            from src.research.messy_document_parser import parse_pdf

            parsed = parse_pdf(filepath)
            if not parsed.text and not parsed.quality.passed:
                logger.error(
                    "Fallback PDF cascade produced no usable text for %s "
                    "(backend=%s reasons=%s). Install: pip install '.[documents]'",
                    filepath,
                    parsed.backend,
                    parsed.quality.reasons,
                )
                if parsed.quality.likely_scanned:
                    logger.error("Likely scanned PDF — OCR backend required")
                return None

            full_text = parsed.markdown or parsed.text
            sections = self._extract_sections_basic(full_text)
            doc_type = self._detect_document_type(full_text)

            tables: list[ParsedTable] = []
            for i, t in enumerate(parsed.tables):
                tables.append(
                    ParsedTable(
                        title=t.title,
                        headers=t.headers,
                        rows=t.rows,
                        page_number=t.page_number,
                        table_index=i,
                    )
                )

            return DoclingDocument(
                source_path=str(filepath),
                title=self._extract_title(full_text, filepath),
                document_type=doc_type,
                content_hash=self._get_content_hash(full_text),
                full_text=full_text,
                sections=sections,
                tables=tables,
                metadata={
                    "source": "fallback",
                    "backend": parsed.backend,
                    "pages": parsed.metadata.get("pages"),
                    "quality": {
                        "passed": parsed.quality.passed,
                        "reasons": list(parsed.quality.reasons),
                        "likely_scanned": parsed.quality.likely_scanned,
                    },
                    "warnings": list(parsed.warnings),
                },
            )

        except Exception as e:
            logger.error(f"Fallback PDF parsing failed for {filepath}: {e}")
            return None

    def _extract_sections_from_docling(self, document: Any) -> list[ParsedSection]:
        """Extract sections from Docling document."""
        sections = []

        try:
            # Iterate through document structure
            for item in document.body:
                if hasattr(item, "label") and "heading" in item.label.lower():
                    level = 1
                    if hasattr(item, "level"):
                        level = item.level

                    section = ParsedSection(
                        title=str(item.text) if hasattr(item, "text") else "Section",
                        content="",
                        level=level,
                        page_start=item.page_no if hasattr(item, "page_no") else 0,
                        page_end=item.page_no if hasattr(item, "page_no") else 0,
                    )
                    sections.append(section)

                elif sections and hasattr(item, "text"):
                    # Add content to current section
                    sections[-1].content += str(item.text) + "\n"

        except Exception as e:
            logger.warning(f"Section extraction error: {e}")

        return sections

    def _extract_sections_basic(self, text: str) -> list[ParsedSection]:
        """Basic section extraction from plain text."""
        sections = []
        current_section = None

        # Pattern for section headings
        heading_pattern = re.compile(
            r"^(?:(?:ITEM|PART|SECTION)\s+[\dIVX]+[.:])?\s*([A-Z][A-Z\s,]+[A-Z])$",
            re.MULTILINE,
        )

        lines = text.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()

            # Check if it's a heading
            if heading_pattern.match(line) and len(line) < 100:
                if current_section:
                    sections.append(current_section)

                current_section = ParsedSection(
                    title=line,
                    content="",
                    level=1,
                    page_start=i // 50,  # Rough estimate
                    page_end=i // 50,
                )
            elif current_section:
                current_section.content += line + "\n"

        if current_section:
            sections.append(current_section)

        return sections

    def _extract_tables_from_docling(self, document: Any) -> list[ParsedTable]:
        """Extract tables from Docling document."""
        tables = []

        try:
            for i, item in enumerate(document.body):
                if hasattr(item, "label") and "table" in item.label.lower():
                    # Try to extract table data
                    if hasattr(item, "table_data"):
                        data = item.table_data
                        headers = data[0] if data else []
                        rows = data[1:] if len(data) > 1 else []

                        table = ParsedTable(
                            title=f"Table {i + 1}",
                            headers=[str(h) for h in headers],
                            rows=[[str(cell) for cell in row] for row in rows],
                            page_number=item.page_no if hasattr(item, "page_no") else 0,
                            table_index=len(tables),
                        )
                        tables.append(table)

        except Exception as e:
            logger.warning(f"Table extraction error: {e}")

        return tables

    def extract_tables(self, doc: DoclingDocument) -> list[Any]:
        """
        Extract all tables as pandas DataFrames.

        Args:
            doc: Parsed DoclingDocument

        Returns:
            List of pandas DataFrames (or dicts if pandas unavailable)
        """
        dataframes = []

        for table in doc.tables:
            df = table.to_dataframe()
            dataframes.append(df)

        return dataframes

    def extract_financials(self, doc: DoclingDocument) -> FinancialMetrics:
        """
        Extract key financial metrics from document.

        Args:
            doc: Parsed DoclingDocument

        Returns:
            FinancialMetrics with extracted values
        """
        metrics = FinancialMetrics()
        text = doc.full_text.lower()

        for metric_name, patterns in self.METRIC_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        value_str = match.group(1).replace(",", "")
                        value = float(value_str)

                        # Handle millions/billions
                        if len(match.groups()) > 1 and match.group(2):
                            multiplier = match.group(2).lower()
                            if multiplier in ("billion", "b"):
                                value *= 1_000_000_000
                            elif multiplier in ("million", "m"):
                                value *= 1_000_000

                        setattr(metrics, metric_name, value)
                        metrics.raw_metrics[metric_name] = match.group(0)
                        break

                    except (ValueError, IndexError):
                        continue

        # Extract fiscal period
        period_match = re.search(
            r"(?:q[1-4]\s*(?:fy)?\s*\d{4}|\d{4}\s*q[1-4]|fiscal\s*(?:year|quarter)\s*\d{4})",
            text,
            re.IGNORECASE,
        )
        if period_match:
            metrics.fiscal_period = period_match.group(0)

        # Extract guidance
        guidance_match = re.search(
            r"(?:guidance|outlook|expects?|forecast)[:\s]+([^.]+\.)",
            text,
            re.IGNORECASE,
        )
        if guidance_match:
            metrics.guidance = guidance_match.group(1).strip()

        return metrics

    def to_rag_chunks(
        self,
        doc: DoclingDocument,
        chunk_size: int = 1000,
        overlap: int = 100,
    ) -> list[dict]:
        """
        Convert document to chunks suitable for RAG ingestion.

        Uses section-aware chunking (LongRAG approach) when possible,
        falling back to sliding window for very long sections.

        Args:
            doc: Parsed DoclingDocument
            chunk_size: Maximum characters per chunk
            overlap: Character overlap between chunks

        Returns:
            List of chunk dictionaries ready for document_aware_rag.py
        """
        chunks = []
        chunk_index = 0

        for section in doc.sections:
            section_text = f"## {section.title}\n\n{section.content}"

            # If section fits in one chunk, keep it together
            if len(section_text) <= chunk_size:
                chunks.append(
                    {
                        "text": section_text,
                        "doc_id": doc.content_hash,
                        "doc_title": doc.title,
                        "section_title": section.title,
                        "section_type": self._classify_section_type(section.title),
                        "chunk_index": chunk_index,
                        "source": doc.source_path,
                        "filename": Path(doc.source_path).name,
                        "content_hash": doc.content_hash,
                        "document_type": doc.document_type,
                        "page_start": section.page_start,
                        "page_end": section.page_end,
                    }
                )
                chunk_index += 1
            else:
                # Split long sections with overlap
                start = 0
                while start < len(section_text):
                    end = min(start + chunk_size, len(section_text))

                    # Try to break at sentence boundary
                    if end < len(section_text):
                        last_period = section_text.rfind(".", start, end)
                        if last_period > start + chunk_size // 2:
                            end = last_period + 1

                    chunk_text = section_text[start:end]

                    chunks.append(
                        {
                            "text": chunk_text,
                            "doc_id": doc.content_hash,
                            "doc_title": doc.title,
                            "section_title": section.title,
                            "section_type": self._classify_section_type(section.title),
                            "chunk_index": chunk_index,
                            "source": doc.source_path,
                            "filename": Path(doc.source_path).name,
                            "content_hash": doc.content_hash,
                            "document_type": doc.document_type,
                            "page_start": section.page_start,
                            "page_end": section.page_end,
                            "is_continuation": start > 0,
                        }
                    )
                    chunk_index += 1
                    start = end - overlap

            # Add table chunks if section has tables
            for table in section.tables:
                table_text = f"**Table: {table.title}**\n\n{table.to_markdown()}"
                chunks.append(
                    {
                        "text": table_text,
                        "doc_id": doc.content_hash,
                        "doc_title": doc.title,
                        "section_title": f"{section.title} - {table.title}",
                        "section_type": "table",
                        "chunk_index": chunk_index,
                        "source": doc.source_path,
                        "filename": Path(doc.source_path).name,
                        "content_hash": doc.content_hash,
                        "document_type": doc.document_type,
                        "page_start": table.page_number,
                        "page_end": table.page_number,
                    }
                )
                chunk_index += 1

        return chunks

    def _classify_section_type(self, title: str) -> str:
        """Classify section type for RAG filtering."""
        title_lower = title.lower()

        if any(kw in title_lower for kw in ["risk", "factor", "uncertainty"]):
            return "risk_factors"
        elif any(kw in title_lower for kw in ["financial", "results", "statement", "balance"]):
            return "financials"
        elif any(kw in title_lower for kw in ["management", "discussion", "analysis", "md&a"]):
            return "mda"
        elif any(kw in title_lower for kw in ["executive", "summary", "overview", "highlight"]):
            return "summary"
        elif any(kw in title_lower for kw in ["outlook", "guidance", "forward", "projection"]):
            return "guidance"
        elif any(kw in title_lower for kw in ["note", "footnote", "accounting"]):
            return "notes"
        else:
            return "content"

    def save_parsed(self, doc: DoclingDocument, output_format: str = "markdown") -> Path:
        """
        Save parsed document to disk.

        Args:
            doc: Parsed DoclingDocument
            output_format: 'markdown', 'json', or 'both'

        Returns:
            Path to saved file
        """
        base_name = Path(doc.source_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        paths = []

        if output_format in ("markdown", "both"):
            md_path = self.output_dir / f"{base_name}_{timestamp}.md"
            md_path.write_text(doc.to_markdown())
            paths.append(md_path)
            logger.info(f"Saved markdown: {md_path}")

        if output_format in ("json", "both"):
            json_path = self.output_dir / f"{base_name}_{timestamp}.json"
            json_data = {
                "document": doc.to_dict(),
                "sections": [
                    {
                        "title": s.title,
                        "content": s.content,
                        "level": s.level,
                        "page_start": s.page_start,
                        "page_end": s.page_end,
                    }
                    for s in doc.sections
                ],
                "tables": [
                    {
                        "title": t.title,
                        "headers": t.headers,
                        "rows": t.rows,
                        "page": t.page_number,
                    }
                    for t in doc.tables
                ],
                "chunks": self.to_rag_chunks(doc),
            }
            json_path.write_text(json.dumps(json_data, indent=2))
            paths.append(json_path)
            logger.info(f"Saved JSON: {json_path}")

        return paths[0] if len(paths) == 1 else paths[0]


# Singleton instance
_parser_instance: Optional[DoclingFinancialParser] = None


def get_docling_parser() -> DoclingFinancialParser:
    """Get or create singleton DoclingFinancialParser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = DoclingFinancialParser()
    return _parser_instance


# CLI interface
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Docling Financial Document Parser")
    parser.add_argument("file", type=str, nargs="?", help="PDF file to parse")
    parser.add_argument(
        "--output",
        choices=["markdown", "json", "both"],
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--extract-financials",
        action="store_true",
        help="Extract financial metrics",
    )
    parser.add_argument(
        "--extract-tables",
        action="store_true",
        help="Extract tables as CSV",
    )
    parser.add_argument(
        "--to-rag",
        action="store_true",
        help="Generate RAG chunks",
    )
    args = parser.parse_args()

    if not args.file:
        print("Usage: python docling_parser.py <pdf_file> [--output markdown|json|both]")
        print("\nOptions:")
        print("  --extract-financials  Extract key financial metrics")
        print("  --extract-tables      Extract tables as DataFrames")
        print("  --to-rag              Generate chunks for RAG ingestion")
        exit(1)

    docling_parser = get_docling_parser()

    print(f"Parsing: {args.file}")
    doc = docling_parser.parse_pdf(args.file)

    if not doc:
        print("Failed to parse document")
        exit(1)

    print(f"\nTitle: {doc.title}")
    print(f"Type: {doc.document_type}")
    print(f"Sections: {len(doc.sections)}")
    print(f"Tables: {len(doc.tables)}")

    if args.extract_financials:
        print("\n=== Financial Metrics ===")
        metrics = docling_parser.extract_financials(doc)
        for key, value in metrics.to_dict().items():
            if value and key != "raw_metrics":
                print(f"  {key}: {value}")

    if args.extract_tables:
        print("\n=== Tables ===")
        tables = docling_parser.extract_tables(doc)
        for i, df in enumerate(tables):
            print(f"\nTable {i + 1}:")
            print(df if hasattr(df, "head") else df.get("headers", []))

    if args.to_rag:
        print("\n=== RAG Chunks ===")
        chunks = docling_parser.to_rag_chunks(doc)
        print(f"Generated {len(chunks)} chunks")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\nChunk {i + 1}: {chunk['section_title']}")
            print(f"  Type: {chunk['section_type']}")
            print(f"  Preview: {chunk['text'][:100]}...")

    # Save output
    output_path = docling_parser.save_parsed(doc, args.output)
    print(f"\nSaved to: {output_path}")
