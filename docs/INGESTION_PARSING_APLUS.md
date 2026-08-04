# Ingestion: Parsing Strategies — A+ Production Spec

**Status:** Production multi-format cascade (2026-08-03)  
**Module:** `src/research/messy_document_parser.py`  
**Pipeline wire:** `DocumentIngestionPipeline.ingest_file()` / `extract_from_path()`  
**Legacy financial wrapper:** `src/research/docling_parser.py` (Docling primary, cascade fallback)

This document is **process truth for document fidelity**, not a profit forecast.  
Cash path remains: put-credit n≥30 → EDGE_CANDIDATE → micro live → scale. See `docs/WORLD_CLASS_PATH_1000_MO.md` when present on branch.

## Goal

World-class extraction for messy docs (PDF, HTML, tables, scanned) so RAG never silently indexes empty or garbage text.

## Cascade (ordered)

| Priority | Backend                            | Formats             | Tables | Install                                 |
| -------- | ---------------------------------- | ------------------- | ------ | --------------------------------------- |
| 1        | IBM Docling                        | PDF (+ layout)      | Yes    | `pip install docling` (optional, heavy) |
| 2        | pdfplumber                         | PDF                 | Yes    | `pip install '.[documents]'`            |
| 3        | pypdf (or PyPDF2)                  | PDF                 | No     | `pip install '.[documents]'`            |
| —        | BeautifulSoup4 / stdlib HTMLParser | HTML                | Yes    | bs4 optional; stdlib always             |
| —        | Plaintext                          | MD/TXT              | N/A    | always                                  |
| OCR      | Explicit **fail / REQUIRES_OCR**   | Image / scanned PDF | —      | not wired until OCR backend chosen      |

## Quality gate (fail closed)

Reject when any of:

- empty extract or `char_count < 40`
- alphanumeric ratio &lt; 0.25 (garbage)
- extreme repeated-character ratio
- PDF with `chars_per_page < 15` → **likely_scanned** (REQUIRES_OCR)

Use `parse_document(path, require_quality_pass=True)` to raise on failure.

## Operator commands

```bash
# Backend inventory
python3 -c "from src.research.messy_document_parser import available_backends; print(available_backends())"

# Parse one file
python3 -c "
from src.research.messy_document_parser import parse_document
d = parse_document('path/to/file.pdf')
print(d.backend, d.quality.passed, d.quality.reasons, len(d.text), len(d.tables))
"

# Ingest into versioned manifest
python3 -c "
from pathlib import Path
from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline
p = DocumentIngestionPipeline()
doc = p.ingest_file(Path('path/to/file.html'))
print(doc.lesson_id, doc.metadata.get('parse_backend'), doc.sha256_hash[:12])
"

# Install lightweight document deps
pip install '.[documents]'
```

## Grade criteria (A+ definition)

| Criterion                       | Required                                         |
| ------------------------------- | ------------------------------------------------ |
| Single entrypoint               | `parse_document` / `ingest_file`                 |
| PDF cascade with real libs      | Docling → pdfplumber → pypdf                     |
| HTML strip + tables             | stdlib and/or bs4                                |
| Table → Markdown appendix       | Yes                                              |
| Empty/scanned never silent pass | Quality gate                                     |
| Provenance                      | `backend`, `quality`, `warnings` on every result |
| Tests                           | `tests/test_messy_document_parser.py`            |
| Optional deps declared          | `pyproject.toml` `[documents]`                   |

## Anti-goals

- Claiming RAG A+ equals trading profitability
- Indexing blank PDF pages as lessons
- Requiring Docling in CI core path (too heavy)
- Fake OCR success without an OCR engine

## Related

- `src/rag/document_ingestion_pipeline.py` — normalize, secret strip, SHA256 versioning
- `src/memory/document_aware_rag.py` — section chunking on clean Markdown
- Controlled experiment: `.claude/rules/controlled-experiment.md`
