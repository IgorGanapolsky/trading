from pathlib import Path
from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline


def test_document_ingestion_normalization_and_secrets(tmp_path):
    manifest_file = tmp_path / "manifest.json"
    pipeline = DocumentIngestionPipeline(manifest_file=manifest_file)

    raw_text = "Lesson LL-999 \nSecret key: sk-abcdefghijklmnopqrstuvwxyz123456 \n"
    file_path = Path("LL-999_Test_Lesson.md")

    doc = pipeline.ingest_document(file_path, raw_text)

    assert doc.lesson_id == "LL-999"
    assert "[REDACTED_SECRET]" in doc.normalized_content
    assert doc.version == 1
    assert doc.is_duplicate is False


def test_document_ingestion_deduplication(tmp_path):
    manifest_file = tmp_path / "manifest.json"
    pipeline = DocumentIngestionPipeline(manifest_file=manifest_file)

    raw_text = "Lesson LL-999 content for deduplication test"
    file_path = Path("LL-999_Test_Lesson.md")

    doc1 = pipeline.ingest_document(file_path, raw_text)
    assert doc1.version == 1
    assert doc1.is_duplicate is False

    doc2 = pipeline.ingest_document(file_path, raw_text)
    assert doc2.version == 1
    assert doc2.is_duplicate is True


def test_document_ingestion_extract_from_markdown_path(tmp_path):
    manifest_file = tmp_path / "manifest.json"
    pipeline = DocumentIngestionPipeline(manifest_file=manifest_file)
    md = tmp_path / "LL-100_note.md"
    md.write_text(
        "# Note\n\nEnough content for markdown extract path to remain stable.\n",
        encoding="utf-8",
    )
    payload = pipeline.extract_from_path(md)
    assert payload["backend"] == "plaintext"
    assert "Enough content" in payload["text"]
