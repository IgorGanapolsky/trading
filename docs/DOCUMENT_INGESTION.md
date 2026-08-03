# Production document ingestion

## Purpose and truth boundary

This pipeline turns local research documents into normalized, provenance-carrying RAG artifacts. It improves the quality and auditability of evidence available to the trading system. It does **not** prove a strategy has edge, authorize live capital, or prove the `$1,000/month after-tax` target has been achieved. Those outcomes remain gated by the paired-trade ledger, the active-strategy cohort, broker state, risk controls, submitted orders, fills, and realized P/L.

## Architecture

```text
local source
  -> size + signature + format validation
  -> format router
       HTML -> Beautiful Soup, boilerplate removal, native tables
       PDF  -> Docling OCR/TableFormer; PyMuPDF text-PDF fallback
       DOCX/images -> Docling
       text/Markdown/CSV/JSON -> deterministic local parsers
  -> structured text + tables + page/bounding-box provenance
  -> extraction quality gate
  -> prompt-injection labeling (document text is untrusted data, never instructions)
  -> Unicode normalization + credential redaction
  -> terminating semantic/table chunker
  -> SHA-256 global dedup + per-source version history
  -> locked atomic manifest + audit artifact
  -> optional reviewed Markdown publication to `rag_knowledge/`
```

The production entrypoint is [`scripts/ingest_document.py`](../scripts/ingest_document.py). The legacy `DoclingFinancialParser` API delegates to the same implementation, so research utilities and the operator path no longer diverge.

## Bogleheads source adapter

[`scripts/bogleheads_research.py`](../scripts/bogleheads_research.py) is the read-only
forum acquisition adapter. It fetches a bounded HTTPS Atom feed, rejects malformed or
off-domain topic URLs, removes active HTML, writes stable Markdown plus a timestamped
JSON receipt under ignored `data/research/`, and sends the Markdown through this same
quality, injection-signal, chunking, deduplication, and versioning path.

```bash
python scripts/bogleheads_research.py --limit 25 --dry-run
python scripts/bogleheads_research.py --limit 25
```

Complete-thread reading and replies use the separate
[`bogleheads-forum-operator`](../skills/bogleheads-forum-operator/SKILL.md) browser
workflow. Feed collection, signed-in reading, a reply draft, and a verified public post
are four distinct evidence surfaces. None is a trading signal or permission to submit
an order.

## Install and verify

The deterministic HTML and text-PDF stack is part of the base project environment. Install the full layout/OCR stack for scanned PDFs, images, and DOCX:

```bash
uv sync --extra dev --extra document-ingestion
python scripts/ingest_document.py --capabilities
pytest tests/test_document_ingestion_pipeline.py -q
pytest tests/test_document_ingestion_docling.py -q
```

`scanned_pdf_ocr`, `images_ocr`, `pdf_layout`, and `docx` must all be `true` on a machine designated for full ingestion. Missing OCR is a hard capability failure, not a silent empty-text success.

## Operator commands

Parse and quality-check without writing a manifest or artifact:

```bash
python scripts/ingest_document.py research/report.pdf --dry-run
```

Register the version and write a redacted audit artifact:

```bash
python scripts/ingest_document.py research/report.pdf
```

Publish normalized Markdown into the RAG source corpus only after the source is reviewed:

```bash
python scripts/ingest_document.py research/report.pdf --publish-to-rag
```

The command returns JSON with the exact parser, media type, content hash, version, quality score, table/chunk counts, duplicate state, and artifact paths. Raw credential-like values are redacted before publication.

## Quality and failure policy

The parser rejects rather than silently indexing:

- unsupported formats or invalid file signatures;
- empty files and empty/near-empty extraction;
- malformed JSON;
- corrupt or password-protected PDFs;
- scanned PDFs when a real OCR backend is unavailable;
- excessive decode-replacement characters;
- invalid chunk overlap that could prevent forward progress;
- corrupt manifests.

PyMuPDF is a deterministic fallback for text-native PDFs. It is not presented as OCR. When embedded text is absent, the parser returns `ocr_required`.

All imported content is labeled `untrusted_document_data`. Common instruction-override, tool-execution, live-order, and secret-exfiltration phrases are recorded as `prompt_injection_signals`; they remain quoted evidence for review and are never promoted to executable agent instructions.

## Table policy

HTML, CSV, PyMuPDF, and Docling tables are normalized to explicit headers and rectangular rows. Each table receives a dedicated retrieval chunk with its title, source page when known, and table index. Oversized tables are split by rows while repeating headers. Standalone tables cannot disappear merely because they were not attached to a section.

## Deduplication and versioning

- Original source bytes receive SHA-256 provenance.
- Normalized, redacted content receives a separate SHA-256 identity.
- Identical content under another filename is recorded as `duplicate_of` and is not treated as new unique evidence.
- Changed content at the same source increments its version.
- Manifest writes use an inter-process lock, a same-directory temporary file, `fsync`, and atomic `os.replace`.
- An unreadable manifest fails closed; it is never silently replaced with an empty index.

## A+ acceptance scorecard

The subsystem earns the internal A+ label only when all ten evidence gates are green on the candidate commit:

|   # | Gate               | Required proof                                                                |
| --: | ------------------ | ----------------------------------------------------------------------------- |
|   1 | Format routing     | PDF, HTML, DOCX, images, text, CSV, and JSON routes are explicit              |
|   2 | Digital PDF        | Real PDF fixture extracts ordered text and page provenance                    |
|   3 | HTML               | Scripts/navigation/boilerplate removed; semantic content retained             |
|   4 | Tables             | Real HTML/PDF tables reconstruct and receive dedicated chunks                 |
|   5 | Scanned documents  | Real image-only PDF fixture passes Docling OCR                                |
|   6 | Quality quarantine | Empty, corrupt, encrypted, malformed, and OCR-required inputs fail closed     |
|   7 | Provenance         | Source hash, parser, page/bbox when available, quality, and warnings recorded |
|   8 | Dedup/versioning   | Cross-path duplicates and changed-source versions are deterministic           |
|   9 | Chunk safety       | Long text terminates, overlap is validated, tables preserve headers           |
|  10 | Operations         | CLI, atomic manifest, audit artifacts, and both CI jobs pass                  |

The required GitHub workflow is `.github/workflows/document-ingestion.yml`. A unit-test result without the real Docling OCR/TableFormer job is not A+ evidence.

## Remaining system-level gates for the money goal

Document quality is only an input layer. Before any `$1,000/month after-tax` real-money claim, independently require:

1. the active put-credit cohort meets the repository's minimum sample and positive expectancy/profit-factor gates;
2. broker state and paired-trade ledgers reconcile;
3. live trading is explicitly unblocked by policy and has funded capital;
4. position sizing, drawdown, inventory, and kill-switch gates pass;
5. actual fills and realized after-tax results demonstrate the monthly outcome.

No ingestion score substitutes for those gates.
