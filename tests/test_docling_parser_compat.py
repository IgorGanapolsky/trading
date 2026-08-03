from __future__ import annotations

import json

import pytest

import src.research.docling_parser as module
from src.rag.document_ingestion_pipeline import (
    DocumentIngestionPipeline,
    ExtractedTable,
    IngestionQualityError,
    ParsedDocument,
)
from src.research.docling_parser import (
    DoclingDocument,
    DoclingFinancialParser,
    ParsedSection,
    ParsedTable,
)


class FakePipeline:
    def __init__(self, parsed: ParsedDocument | None = None, error: Exception | None = None):
        self.parsed = parsed
        self.error = error

    def parse_file(self, _path):
        if self.error:
            raise self.error
        return self.parsed


def structured_parsed() -> ParsedDocument:
    table = ExtractedTable(
        "Quarterly Results",
        ("Quarter", "Revenue"),
        (("Q1", "$90 million"), ("Q2", "$100 million")),
        0,
        2,
        {"page_number": 2},
    )
    return ParsedDocument(
        source_path="report.pdf",
        source_sha256="c" * 64,
        title="ACME Q2 Results",
        media_type="application/pdf",
        parser="docling",
        text=(
            "# ACME Q2 Results\n\n## Financial Results\n\n"
            "Revenue: $100 million\nNet income: $20 million\n"
            "Diluted EPS: $1.25\nAdjusted EBITDA: $30 million\n"
            "Gross margin: 42%\nOperating margin: 18%\n"
            "Guidance: Revenue is expected to increase next quarter.\nQ2 2026"
        ),
        tables=(table,),
        provenance=({"kind": "TextItem", "page_number": 1},),
        metadata={"quality_gate": "passed"},
        warnings=("fixture_warning",),
        quality_score=0.97,
        ocr_enabled=True,
    )


def test_parsed_table_dataframe_and_markdown():
    table = ParsedTable("Revenue", ["Q", "Value"], [["Q1", "$1m"]], 3, 0)

    frame = table.to_dataframe()

    assert list(frame.columns) == ["Q", "Value"]
    assert frame.iloc[0]["Value"] == "$1m"
    assert "| Q | Value |" in table.to_markdown()


def test_docling_document_serialization_and_linked_table_rendering():
    table = ParsedTable("Revenue", ["Q", "Value"], [["Q1", "$1m"]], 1, 0)
    section = ParsedSection("Results", "Strong quarter.", 1, 1, 1, tables=[table])
    document = DoclingDocument(
        source_path="report.pdf",
        title="Report",
        document_type="earnings_report",
        content_hash="d" * 64,
        full_text="Strong quarter.",
        sections=[section],
        tables=[table],
        metadata={"parser": "fixture"},
    )

    payload = document.to_dict()
    markdown = document.to_markdown()

    assert payload["section_count"] == 1
    assert payload["table_count"] == 1
    assert markdown.count("**Table: Revenue**") == 1
    assert "## Results" in markdown


def test_parse_document_routes_structured_output_and_metadata(tmp_path):
    parser = DoclingFinancialParser(output_dir=tmp_path, pipeline=FakePipeline(structured_parsed()))

    document = parser.parse_document("report.pdf")

    assert document is not None
    assert document.document_type == "earnings_report"
    assert document.title == "ACME Q2 Results"
    assert len(document.sections) == 2
    assert document.tables[0].page_number == 2
    assert document.metadata["parser"] == "docling"
    assert document.metadata["quality_score"] == 0.97
    assert document.metadata["ocr_enabled"] is True
    assert document.metadata["warnings"] == ["fixture_warning"]


def test_parse_document_returns_none_on_quality_failure(tmp_path):
    parser = DoclingFinancialParser(
        output_dir=tmp_path,
        pipeline=FakePipeline(error=IngestionQualityError("bad", code="empty_extraction")),
    )

    assert parser.parse_document("bad.pdf") is None


def test_parse_pdf_routes_non_pdf_to_actual_format(tmp_path, caplog):
    parser = DoclingFinancialParser(output_dir=tmp_path, pipeline=FakePipeline(structured_parsed()))

    document = parser.parse_pdf("report.html")

    assert document is not None
    assert "non-PDF" in caplog.text


def test_section_fallback_for_plain_text(tmp_path):
    parser = DoclingFinancialParser(output_dir=tmp_path, pipeline=FakePipeline())

    assert parser._sections_from_markdown("Plain document content.") == [
        ParsedSection("Document", "Plain document content.", 1, 1, 1)
    ]
    assert parser._sections_from_markdown("   ") == []


def test_extract_financials_handles_units_period_and_guidance(tmp_path):
    parser = DoclingFinancialParser(output_dir=tmp_path, pipeline=FakePipeline())
    parsed = structured_parsed()
    document = DoclingDocument(
        parsed.source_path,
        parsed.title,
        "earnings_report",
        parsed.source_sha256,
        parsed.text,
        [],
        [],
        {},
    )

    metrics = parser.extract_financials(document)

    assert metrics.revenue == 100_000_000
    assert metrics.net_income == 20_000_000
    assert metrics.eps == 1.25
    assert metrics.ebitda == 30_000_000
    assert metrics.gross_margin == 42
    assert metrics.operating_margin == 18
    assert metrics.fiscal_period == "Q2 2026"
    assert metrics.guidance == "Revenue is expected to increase next quarter."
    assert metrics.to_dict()["raw_metrics"]["revenue"].startswith("Revenue")


def test_to_rag_chunks_and_save_all_formats(tmp_path):
    actual_pipeline = DocumentIngestionPipeline(
        manifest_file=tmp_path / "manifest.json", min_text_chars=10
    )
    parser = DoclingFinancialParser(output_dir=tmp_path, pipeline=actual_pipeline)
    parsed = structured_parsed()
    document = DoclingDocument(
        parsed.source_path,
        parsed.title,
        "earnings_report",
        parsed.source_sha256,
        parsed.text,
        parser._sections_from_markdown(parsed.text),
        [parser._compat_table(parsed.tables[0])],
        {"parser": "docling", "media_type": "application/pdf", "quality_score": 0.97},
    )

    chunks = parser.to_rag_chunks(document, chunk_size=256, overlap=32)
    markdown_path = parser.save_parsed(document, "both")
    json_path = markdown_path.with_suffix(".json")

    assert chunks
    assert any(chunk["chunk_type"] == "table" for chunk in chunks)
    assert markdown_path.exists()
    assert json_path.exists()
    saved = json.loads(json_path.read_text())
    assert saved["document"]["title"] == "ACME Q2 Results"
    assert saved["chunks"]

    json_only = parser.save_parsed(document, "json")
    assert json_only.suffix == ".json"
    with pytest.raises(ValueError, match="output_format"):
        parser.save_parsed(document, "xml")


def test_singleton_factory_reuses_parser(monkeypatch):
    monkeypatch.setattr(module, "_parser_instance", None)

    first = module.get_docling_parser()
    second = module.get_docling_parser()

    assert first is second
