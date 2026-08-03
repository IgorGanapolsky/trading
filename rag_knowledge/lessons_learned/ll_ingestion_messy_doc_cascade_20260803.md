# LL-INGEST-001: Messy document parse must fail closed (not silent empty)

**Severity**: HIGH  
**Date**: 2026-08-03  
**Tags**: `rag`, `ingestion`, `pdf`, `html`, `quality-gate`, `ocr`

## What happened

Document ingestion for financial PDFs advertised Docling + PyPDF2/pdfplumber fallbacks, but:

1. Docling / PyPDF2 / pdfplumber were often **not installed**
2. Fallback imported `PyPDF2` while the environment had `pypdf`
3. HTML parsing was explicitly unused (`beautifulsoup` commented as never imported)
4. Scanned/image docs had **no OCR path** and could fail silently
5. Production RAG path only reliably parsed **clean Markdown lessons**

Grade for messy docs was **C+ design / D runtime**.

## Root cause

Research parser code existed without a **single production cascade**, quality gate, dependency extra, or tests that prove fail-closed behavior on empty extracts.

## Prevention

1. Always use `src/research/messy_document_parser.parse_document()` / `DocumentIngestionPipeline.ingest_file()`
2. Quality gate: reject empty, low alnum, likely-scanned (`REQUIRES_OCR`)
3. Install `pip install '.[documents]'` on machines that ingest PDFs
4. Never claim A+ parsing without green `tests/test_messy_document_parser.py`
5. Do not confuse document-fidelity A+ with trading cash-engine A+ (needs EDGE_CANDIDATE)

## Action

- Code: `messy_document_parser.py`, pipeline wire, docling fallback delegation
- Spec: `docs/INGESTION_PARSING_APLUS.md`
- Deps: `pyproject.toml` optional `[documents]`
