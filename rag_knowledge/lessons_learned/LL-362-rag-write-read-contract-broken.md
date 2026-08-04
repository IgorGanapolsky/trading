# LL-362: RAG Write/Read Contract Was Broken and the Health Check Was Right

**Date**: August 3, 2026
**Category**: RAG / Data Integrity / Verification
**Severity**: CRITICAL
**Related**: LL-361, data-integrity.md, compound-engineering.md

## Summary

`system_health_check.py` reported **"RAG System: BROKEN — write/read round trip failed"**
and held `make dry-run` red. It was a true positive that had been treated as noise.

`LessonsLearnedRAG.add_lesson()` wrote the markdown file and refreshed the legacy
keyword list, but never re-indexed the `TradingRAGPipeline` that `query()` actually
reads from. The lesson existed on disk and was **unretrievable**. Every lesson captured
at runtime was invisible to the very next retrieval.

## The three defects found, same investigation

| #   | Defect                                                         | Impact                                                               |
| --- | -------------------------------------------------------------- | -------------------------------------------------------------------- |
| 1   | `add_lesson()` did not re-index the pipeline                   | Writes invisible to reads                                            |
| 2   | `query()` returned pipeline rows without setting `last_source` | CLI reported `source: "none"` beside real results — a provenance lie |
| 3   | Test/health fixtures lacked a severity or prevention section   | `quality_gate()` correctly rejected them; looked like a search bug   |

Defect 3 appeared **three separate times** (a CLI test fixture, the health probe, and
a lessons fixture). Fixtures written before a gate existed do not fail loudly — they
fail as a plausible-looking empty result.

## Root Cause

The write path and the read path were never exercised together in a test. Each side had
coverage; the contract between them had none. The one check that did exercise it — the
health probe — was failing and had been tolerated.

## Prevention

1. `add_lesson()` now re-indexes the pipeline after writing. Locked by
   `test_add_lesson_is_immediately_retrievable`.
2. `query()` records `last_source = "pipeline"` on the primary path. Locked by
   `test_last_source_is_never_none_when_results_are_returned`.
3. Fixtures must satisfy `quality_gate()` (severity marker + prevention/action section)
   or they are silently dropped at ingestion.
4. `make dry-run` runs `system_health_check.py`, which now genuinely exercises the round
   trip instead of failing on an invalid probe.

## Rule

**A red check is evidence until proven otherwise.** "That check is always broken" is a
claim requiring the same verification as any other. Here it was correct, and the cost of
having dismissed it was that runtime-captured lessons were unretrievable.

**Never repair a failing probe by weakening it.** The first fix attempted was to make
the probe lesson valid; that was necessary but not sufficient, and stopping there would
have turned a true positive into a green light over a still-broken system.

## Verification

```bash
python scripts/system_health_check.py     # ALL CHECKS PASSED
python -m pytest tests/test_query_lessons_learned.py -q
make lint
```
