"""Full-stack Docling acceptance tests.

These tests are isolated from the lightweight trading runtime but are required
by the document-ingestion workflow. They prove actual OCR and TableFormer
behavior instead of merely mocking adapter calls.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline

fitz = pytest.importorskip("fitz")
pytest.importorskip("docling")

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(scope="module")
def docling_pipeline(tmp_path_factory: pytest.TempPathFactory) -> DocumentIngestionPipeline:
    root = tmp_path_factory.mktemp("docling-ingestion")
    return DocumentIngestionPipeline(
        manifest_file=root / "manifest.json",
        min_text_chars=20,
        prefer_docling=True,
    )


def _make_scanned_pdf(path: Path) -> None:
    text_pdf = fitz.open()
    page = text_pdf.new_page(width=612, height=792)
    page.insert_text((72, 120), "SCANNED REVENUE EVIDENCE", fontsize=24)
    page.insert_text((72, 170), "Quarterly revenue increased to 100 million dollars.", fontsize=16)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)

    scanned_pdf = fitz.open()
    scanned_page = scanned_pdf.new_page(width=612, height=792)
    scanned_page.insert_image(scanned_page.rect, pixmap=pixmap)
    scanned_pdf.save(path)
    scanned_pdf.close()
    text_pdf.close()


def _make_table_pdf(path: Path) -> None:
    pdf = fitz.open()
    page = pdf.new_page(width=612, height=792)
    page.insert_text((72, 72), "ACME QUARTERLY RESULTS", fontsize=18)
    x_positions = (72, 210, 360)
    y_positions = (120, 165, 210, 255)
    for x in x_positions:
        page.draw_line((x, y_positions[0]), (x, y_positions[-1]), width=1.2)
    for y in y_positions:
        page.draw_line((x_positions[0], y), (x_positions[-1], y), width=1.2)
    cells = (
        ("Quarter", "Revenue"),
        ("Q1", "$90m"),
        ("Q2", "$100m"),
    )
    for row_index, row in enumerate(cells):
        baseline = y_positions[row_index] + 29
        page.insert_text((82, baseline), row[0], fontsize=12)
        page.insert_text((220, baseline), row[1], fontsize=12)
    page.insert_text((72, 300), "Management raised full-year revenue guidance.", fontsize=12)
    pdf.save(path)
    pdf.close()


def test_docling_ocr_extracts_image_only_pdf(
    tmp_path: Path, docling_pipeline: DocumentIngestionPipeline
) -> None:
    source = tmp_path / "scanned.pdf"
    _make_scanned_pdf(source)

    parsed = docling_pipeline.parse_file(source)

    normalized = re.sub(r"\s+", " ", parsed.text).upper()
    assert parsed.parser == "docling"
    assert parsed.ocr_enabled is True
    assert "SCANNED REVENUE EVIDENCE" in normalized
    assert parsed.metadata["quality_gate"] == "passed"
    assert parsed.provenance


def test_docling_reconstructs_financial_table(
    tmp_path: Path, docling_pipeline: DocumentIngestionPipeline
) -> None:
    source = tmp_path / "table.pdf"
    _make_table_pdf(source)

    parsed = docling_pipeline.parse_file(source)
    chunks = docling_pipeline.chunk_document(parsed, chunk_size=512, overlap=64)

    assert parsed.parser == "docling"
    assert parsed.tables
    rendered = "\n".join(table.to_markdown() for table in parsed.tables)
    assert "Quarter" in rendered
    assert "Q2" in rendered
    assert "100m" in rendered
    assert any(chunk.chunk_type == "table" for chunk in chunks)
