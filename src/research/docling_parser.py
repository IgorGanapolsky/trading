"""Compatibility facade for structured financial-document parsing.

Historically this module instantiated Docling directly and then inspected the
removed ``document.body``/``table_data`` APIs. The production parser now lives
in :mod:`src.rag.document_ingestion_pipeline`; this facade preserves the public
research API while routing every format through the tested ingestion path.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.rag.document_ingestion_pipeline import (
    DocumentIngestionPipeline,
    ExtractedTable,
    ParsedDocument,
)

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parents[2]
PARSED_DIR = PROJECT_DIR / "data" / "research" / "parsed_documents"


@dataclass(frozen=True)
class ParsedTable:
    title: str
    headers: list[str]
    rows: list[list[str]]
    page_number: int
    table_index: int
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dataframe(self) -> Any:
        try:
            import pandas as pd

            return pd.DataFrame(self.rows, columns=self.headers)
        except ImportError:
            return {"headers": self.headers, "rows": self.rows}

    def to_markdown(self) -> str:
        return ExtractedTable(
            self.title,
            tuple(self.headers),
            tuple(tuple(row) for row in self.rows),
            self.table_index,
            self.page_number,
            self.provenance,
        ).to_markdown()


@dataclass
class FinancialMetrics:
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None
    ebitda: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    debt_to_equity: float | None = None
    free_cash_flow: float | None = None
    guidance: str | None = None
    fiscal_period: str | None = None
    raw_metrics: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedSection:
    title: str
    content: str
    level: int
    page_start: int
    page_end: int
    tables: list[ParsedTable] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DoclingDocument:
    source_path: str
    title: str
    document_type: str
    content_hash: str
    full_text: str
    sections: list[ParsedSection]
    tables: list[ParsedTable]
    metadata: dict[str, Any]
    parsed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "title": self.title,
            "document_type": self.document_type,
            "content_hash": self.content_hash,
            "full_text": self.full_text,
            "section_count": len(self.sections),
            "table_count": len(self.tables),
            "metadata": self.metadata,
            "parsed_at": self.parsed_at.isoformat(),
        }

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"**Source**: {Path(self.source_path).name}", ""]
        for section in self.sections:
            lines.extend(
                [f"{'#' * min(section.level + 1, 6)} {section.title}", "", section.content, ""]
            )
            for table in section.tables:
                lines.extend([table.to_markdown(), ""])
        linked = {table.table_index for section in self.sections for table in section.tables}
        for table in self.tables:
            if table.table_index not in linked:
                lines.extend([table.to_markdown(), ""])
        return "\n".join(lines).strip()


class DoclingFinancialParser:
    """Financial research API backed by the production ingestion router."""

    DOCUMENT_TYPE_PATTERNS = {
        "sec_filing": (
            r"form\s*10-[kq]",
            r"form\s*8-k",
            r"securities\s*and\s*exchange\s*commission",
            r"\bedgar\b",
        ),
        "earnings_report": (
            r"earnings\s*release",
            r"quarterly\s*results",
            r"financial\s*results",
            r"q[1-4]\s*\d{4}",
        ),
        "fed_minutes": (
            r"federal\s*reserve",
            r"fomc\s*minutes",
            r"federal\s*open\s*market\s*committee",
            r"monetary\s*policy",
        ),
    }
    METRIC_PATTERNS = {
        "revenue": (
            r"(?:total\s*)?revenue[:\s]+\$?\(?([\d,]+\.?\d*)\)?\s*(million|billion|M|B)?",
            r"net\s*sales[:\s]+\$?\(?([\d,]+\.?\d*)\)?\s*(million|billion|M|B)?",
        ),
        "net_income": (r"net\s*income[:\s]+\$?\(?([\d,]+\.?\d*)\)?\s*(million|billion|M|B)?",),
        "eps": (r"(?:diluted\s*)?(?:eps|earnings\s*per\s*share)[:\s]+\$?\(?([\d,]+\.?\d*)\)?",),
        "ebitda": (
            r"(?:adjusted\s*)?ebitda[:\s]+\$?\(?([\d,]+\.?\d*)\)?\s*(million|billion|M|B)?",
        ),
        "gross_margin": (r"gross\s*(?:profit\s*)?margin[:\s]+([\d,]+\.?\d*)\s*%?",),
        "operating_margin": (r"op(?:erating)?\s*margin[:\s]+([\d,]+\.?\d*)\s*%?",),
    }

    def __init__(
        self,
        output_dir: Path | None = None,
        *,
        pipeline: DocumentIngestionPipeline | None = None,
    ) -> None:
        self.output_dir = output_dir or PARSED_DIR
        self.pipeline = pipeline or DocumentIngestionPipeline()

    def parse_document(self, path: str | Path) -> DoclingDocument | None:
        try:
            parsed = self.pipeline.parse_file(path)
        except Exception as exc:
            logger.error("Document parsing failed for %s: %s", path, exc)
            return None
        tables = [self._compat_table(table) for table in parsed.tables]
        sections = self._sections_from_markdown(parsed.text)
        document_type = self._detect_document_type(parsed.text)
        metadata = {
            **parsed.metadata,
            "parser": parsed.parser,
            "media_type": parsed.media_type,
            "quality_score": parsed.quality_score,
            "warnings": list(parsed.warnings),
            "ocr_enabled": parsed.ocr_enabled,
            "provenance": list(parsed.provenance),
        }
        return DoclingDocument(
            source_path=parsed.source_path,
            title=parsed.title,
            document_type=document_type,
            content_hash=parsed.source_sha256,
            full_text=parsed.text,
            sections=sections,
            tables=tables,
            metadata=metadata,
        )

    def parse_pdf(self, path: str | Path) -> DoclingDocument | None:
        if Path(path).suffix.lower() != ".pdf":
            logger.warning("parse_pdf received non-PDF input; routing by actual format")
        return self.parse_document(path)

    def _compat_table(self, table: ExtractedTable) -> ParsedTable:
        return ParsedTable(
            title=table.title,
            headers=list(table.headers),
            rows=[list(row) for row in table.rows],
            page_number=table.page_number or 0,
            table_index=table.table_index,
            provenance=table.provenance,
        )

    def _detect_document_type(self, text: str) -> str:
        lowered = text.lower()
        for document_type, patterns in self.DOCUMENT_TYPE_PATTERNS.items():
            if any(re.search(pattern, lowered) for pattern in patterns):
                return document_type
        return "other"

    def _sections_from_markdown(self, text: str) -> list[ParsedSection]:
        headings = list(re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE))
        if not headings:
            return [ParsedSection("Document", text, 1, 1, 1)] if text.strip() else []
        sections: list[ParsedSection] = []
        for index, match in enumerate(headings):
            start = match.end()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            sections.append(
                ParsedSection(
                    title=match.group(2).strip(),
                    content=text[start:end].strip(),
                    level=len(match.group(1)),
                    page_start=0,
                    page_end=0,
                )
            )
        return sections

    def extract_tables(self, doc: DoclingDocument) -> list[Any]:
        return [table.to_dataframe() for table in doc.tables]

    def extract_financials(self, doc: DoclingDocument) -> FinancialMetrics:
        metrics = FinancialMetrics()
        text = doc.full_text
        for metric_name, patterns in self.METRIC_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if not match:
                    continue
                try:
                    value = float(match.group(1).replace(",", ""))
                except (ValueError, IndexError):
                    continue
                unit = match.group(2).lower() if len(match.groups()) > 1 and match.group(2) else ""
                if unit in {"billion", "b"}:
                    value *= 1_000_000_000
                elif unit in {"million", "m"}:
                    value *= 1_000_000
                setattr(metrics, metric_name, value)
                metrics.raw_metrics[metric_name] = match.group(0)
                break
        period = re.search(
            r"(?:q[1-4]\s*(?:fy)?\s*\d{4}|\d{4}\s*q[1-4]|fiscal\s*(?:year|quarter)\s*\d{4})",
            text,
            re.IGNORECASE,
        )
        if period:
            metrics.fiscal_period = period.group(0)
        guidance = re.search(
            r"(?:guidance|outlook|expects?|forecast)[:\s]+([^.]+\.)", text, re.IGNORECASE
        )
        if guidance:
            metrics.guidance = guidance.group(1).strip()
        return metrics

    def to_rag_chunks(
        self,
        doc: DoclingDocument,
        chunk_size: int = 1_200,
        overlap: int = 120,
    ) -> list[dict[str, Any]]:
        tables = tuple(
            ExtractedTable(
                table.title,
                tuple(table.headers),
                tuple(tuple(row) for row in table.rows),
                table.table_index,
                table.page_number,
                table.provenance,
            )
            for table in doc.tables
        )
        parsed = ParsedDocument(
            source_path=doc.source_path,
            source_sha256=doc.content_hash,
            title=doc.title,
            media_type=str(doc.metadata.get("media_type", "application/octet-stream")),
            parser=str(doc.metadata.get("parser", "document-ingestion")),
            text=doc.full_text,
            tables=tables,
            metadata=doc.metadata,
            quality_score=float(doc.metadata.get("quality_score", 1.0)),
        )
        return [
            asdict(chunk)
            for chunk in self.pipeline.chunk_document(
                parsed, chunk_size=chunk_size, overlap=overlap
            )
        ]

    def save_parsed(self, doc: DoclingDocument, output_format: str = "markdown") -> Path:
        if output_format not in {"markdown", "json", "both"}:
            raise ValueError("output_format must be markdown, json, or both")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        base = Path(doc.source_path).stem
        content_hash = doc.content_hash[:12]
        markdown_path = self.output_dir / f"{base}-{content_hash}.md"
        json_path = self.output_dir / f"{base}-{content_hash}.json"
        if output_format in {"markdown", "both"}:
            markdown_path.write_text(doc.to_markdown() + "\n", encoding="utf-8")
        if output_format in {"json", "both"}:
            payload = {
                "document": doc.to_dict(),
                "sections": [asdict(section) for section in doc.sections],
                "tables": [asdict(table) for table in doc.tables],
                "chunks": self.to_rag_chunks(doc),
            }
            json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return json_path if output_format == "json" else markdown_path


_parser_instance: DoclingFinancialParser | None = None


def get_docling_parser() -> DoclingFinancialParser:
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = DoclingFinancialParser()
    return _parser_instance


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Parse a financial research document")
    parser.add_argument("file", type=Path)
    parser.add_argument("--output", choices=["markdown", "json", "both"], default="markdown")
    parser.add_argument("--extract-financials", action="store_true")
    parser.add_argument("--to-rag", action="store_true")
    args = parser.parse_args()

    financial_parser = get_docling_parser()
    document = financial_parser.parse_document(args.file)
    if document is None:
        return 1
    print(
        json.dumps(
            {
                "title": document.title,
                "type": document.document_type,
                "sections": len(document.sections),
                "tables": len(document.tables),
                "parser": document.metadata.get("parser"),
                "quality_score": document.metadata.get("quality_score"),
            },
            indent=2,
        )
    )
    if args.extract_financials:
        print(json.dumps(financial_parser.extract_financials(document).to_dict(), indent=2))
    if args.to_rag:
        print(f"chunks={len(financial_parser.to_rag_chunks(document))}")
    output = financial_parser.save_parsed(document, args.output)
    print(f"saved={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
