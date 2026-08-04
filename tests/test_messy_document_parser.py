"""Tests for multi-format messy document parser (production cascade)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.research.messy_document_parser import (
    assess_quality,
    available_backends,
    detect_format,
    parse_document,
    parse_html,
    parse_image,
    parse_text_file,
    parse_to_rag_payload,
)


def test_available_backends_reports_stdlib_always():
    backends = available_backends()
    assert backends["html_stdlib"] is True
    assert backends["plaintext"] is True
    assert set(backends) >= {"docling", "pdfplumber", "pypdf", "bs4", "html_stdlib"}


def test_detect_format_by_suffix():
    assert detect_format(Path("a.pdf")) == "pdf"
    assert detect_format(Path("a.HTML")) == "html"
    assert detect_format(Path("note.md")) == "markdown"
    assert detect_format(Path("scan.png")) == "image"


def test_assess_quality_rejects_empty():
    q = assess_quality("")
    assert q.passed is False
    assert q.empty_extract is True


def test_assess_quality_rejects_low_alnum_garbage():
    garbage = ".... .... .... !!!! @@@@ #### $$$$ %%%% " * 20
    q = assess_quality(garbage, min_chars=40)
    assert q.passed is False
    assert q.garbage is True


def test_assess_quality_flags_likely_scanned_pdf():
    thin = "x" * 10  # very little text
    q = assess_quality(thin, page_count=5, min_chars=5, format_hint="pdf")
    assert q.likely_scanned is True
    assert q.passed is False


def test_assess_quality_passes_normal_prose():
    text = (
        "Berkshire Hathaway annual letter discusses float, insurance, and "
        "owner earnings with substantial narrative detail for investors."
    )
    q = assess_quality(text)
    assert q.passed is True
    assert q.empty_extract is False
    assert q.garbage is False


def test_parse_html_strips_scripts_and_extracts_table(tmp_path: Path):
    html = """<!DOCTYPE html>
    <html><head><script>evil()</script><style>.x{color:red}</style></head>
    <body>
      <nav>Skip me</nav>
      <h1>Q4 Earnings</h1>
      <p>Revenue grew year over year for the reporting period.</p>
      <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Revenue</td><td>100</td></tr>
        <tr><td>EPS</td><td>2.5</td></tr>
      </table>
    </body></html>
    """
    path = tmp_path / "earnings.html"
    path.write_text(html, encoding="utf-8")

    doc = parse_html(path)
    assert doc.format == "html"
    assert doc.backend in {"html_stdlib", "bs4"}
    assert "Revenue grew" in doc.text
    assert "evil()" not in doc.text
    # Chrome tags must be stripped on both stdlib and bs4 paths
    assert "Skip me" not in doc.text
    assert doc.quality.passed is True
    assert len(doc.tables) >= 1
    assert "Revenue" in doc.tables[0].headers or any("Revenue" in row for row in doc.tables[0].rows)
    assert "Extracted Tables" in doc.markdown or "|" in doc.markdown


def test_parse_pdf_continues_past_short_docling_extract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Short Docling extract must not block pdfplumber/pypdf fallback (Codex P1)."""
    from src.research import messy_document_parser as mdp

    pdf_path = tmp_path / "short-then-good.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    long_text = (
        "Berkshire Hathaway shareholder letter discusses insurance float and "
        "owner earnings with substantial narrative detail for investors."
    )

    def fake_docling(_path: Path):
        return ("tiny", [], {"pages": 0, "backend_detail": "docling-stub"})

    def fake_pdfplumber(_path: Path):
        return (long_text, [], {"pages": 1, "backend_detail": "pdfplumber-stub"})

    def fake_pypdf(_path: Path):
        raise AssertionError("pypdf should not run after pdfplumber quality pass")

    monkeypatch.setattr(mdp, "_extract_pdf_docling", fake_docling)
    monkeypatch.setattr(mdp, "_extract_pdf_pdfplumber", fake_pdfplumber)
    monkeypatch.setattr(mdp, "_extract_pdf_pypdf", fake_pypdf)

    doc = mdp.parse_pdf(pdf_path)
    assert doc.backend == "pdfplumber"
    assert doc.quality.passed is True
    assert "insurance float" in doc.text
    assert doc.metadata.get("attempts") == ["docling", "pdfplumber"]
    assert any("docling_quality_fail" in w for w in doc.warnings)


def test_parse_html_string_without_path():
    doc = parse_html(
        html="<html><body><p>Standalone HTML body with enough characters here.</p></body></html>"
    )
    assert "Standalone HTML" in doc.text
    assert doc.quality.passed is True


def test_parse_markdown_file(tmp_path: Path):
    path = tmp_path / "LL-999_Test.md"
    path.write_text(
        "# Lesson\n\n**Severity**: HIGH\n\n## Prevention\nDo not skip inventory audit.\n",
        encoding="utf-8",
    )
    doc = parse_text_file(path)
    assert doc.format == "markdown"
    assert doc.backend == "plaintext"
    assert "inventory" in doc.text
    assert doc.quality.passed is True


def test_parse_image_requires_ocr(tmp_path: Path):
    path = tmp_path / "scan.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    doc = parse_image(path)
    assert doc.format == "image"
    assert doc.quality.passed is False
    assert "REQUIRES_OCR" in doc.warnings or "REQUIRES_OCR" in doc.quality.reasons


def test_parse_document_dispatches_html(tmp_path: Path):
    path = tmp_path / "doc.htm"
    path.write_text(
        "<html><body><p>Dispatch path works for HTML documents with content.</p></body></html>",
        encoding="utf-8",
    )
    doc = parse_document(path)
    assert doc.format == "html"
    assert doc.quality.passed is True


def test_parse_document_missing_file(tmp_path: Path):
    missing = tmp_path / "definitely-does-not-exist-xyz.pdf"
    with pytest.raises(FileNotFoundError):
        parse_document(missing)


def test_require_quality_pass_raises(tmp_path: Path):
    path = tmp_path / "empty.html"
    path.write_text("<html><body></body></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="quality gate"):
        parse_document(path, require_quality_pass=True)


def test_parse_to_rag_payload_keys(tmp_path: Path):
    path = tmp_path / "note.md"
    path.write_text(
        "Enough markdown content for the rag payload path to succeed cleanly.\n",
        encoding="utf-8",
    )
    payload = parse_to_rag_payload(path, require_quality_pass=True)
    assert payload["format"] == "markdown"
    assert payload["backend"] == "plaintext"
    assert "text" in payload
    assert "quality" in payload


def test_parse_pdf_blank_fails_quality_closed(tmp_path: Path):
    pytest.importorskip("pypdf")
    from pypdf import PdfWriter

    # Blank page: must not claim quality pass with empty text (fail closed).
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as f:
        writer.write(f)

    doc = parse_document(pdf_path)
    assert doc.format == "pdf"
    assert doc.backend in {"pypdf", "pdfplumber", "docling", "none"}
    if not doc.text.strip():
        assert doc.quality.passed is False
        assert doc.quality.empty_extract or "empty" in " ".join(doc.quality.reasons)


def test_parse_pdf_with_text_content(tmp_path: Path):
    """If reportlab available, build a real text PDF; else skip."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "letter.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(
        72,
        720,
        "Berkshire Hathaway shareholder letter discusses insurance float and capital allocation.",
    )
    c.drawString(72, 700, "Second line of substantive financial narrative content.")
    c.save()

    doc = parse_document(pdf_path)
    assert doc.format == "pdf"
    assert doc.backend in {"pypdf", "pdfplumber", "docling"}
    # pypdf may or may not extract depending on encoding; if text present must pass
    if len(doc.text) >= 40:
        assert doc.quality.passed is True
        assert "Berkshire" in doc.text or "insurance" in doc.text.lower()


def test_pipeline_ingest_file_html(tmp_path: Path):
    from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline

    html_path = tmp_path / "LL-9001_earnings.html"
    html_path.write_text(
        "<html><body><p>Pipeline ingest of HTML with enough characters for the gate.</p>"
        "<table><tr><th>A</th></tr><tr><td>1</td></tr></table></body></html>",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    pipe = DocumentIngestionPipeline(manifest_file=manifest)
    doc = pipe.ingest_file(html_path)
    assert doc.lesson_id == "LL-9001"
    assert "Pipeline ingest" in doc.normalized_content
    assert doc.metadata.get("parse_backend") in {"html_stdlib", "bs4"}
    assert doc.metadata.get("parse_format") == "html"
