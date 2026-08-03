# LL-361: Document Ingestion Requires Real Parser Proof Gates

**ID**: LL-361
**Date**: 2026-08-03
**Severity**: HIGH
**Category**: RAG, document ingestion, production verification
**Status**: ACTIVE

## Incident Summary

The repository exposed a production-sounding ingestion pipeline that only normalized
already-extracted text. A separate experimental Docling wrapper was not connected to
the production path, used stale API assumptions, and had no real OCR or table-model
acceptance test. The legacy chunk loop could also stop making progress on a long
section.

## Root Cause

Parser availability, parser integration, and production evidence were conflated.
Unit tests around normalization and deduplication proved none of the hard cases:
image-only PDFs, layout-aware tables, corrupt inputs, provenance, atomic manifests,
or untrusted prompt-like document content.

## Prevention Rule

Do not grade document ingestion as production-ready until one versioned path proves
all of the following:

1. Format routing and input validation happen before extraction.
2. OCR and table reconstruction run through the actual optional model stack.
3. Every chunk retains source, page, parser, and table provenance where available.
4. Empty, corrupt, encrypted, or image-only-without-OCR inputs fail closed.
5. Normalization, secret redaction, and prompt-injection signaling treat document
   text as untrusted data.
6. Chunking has a tested forward-progress invariant.
7. Content identity and source version history survive renames and updates.
8. Manifest writes are locked, atomic, and recoverable from process interruption.
9. CI has both deterministic fast tests and real OCR/table model tests.
10. Ingestion quality is reported separately from trading expectancy, live fills,
    taxes, and realized profit.

## Operator Trust Rule

A parser library in dependencies is capability potential, not proof. Require a real
image-only OCR assertion and a real financial-table reconstruction assertion before
calling the full ingestion stack available. Never translate that evidence into a
profit claim; strategy and broker gates remain independent.
