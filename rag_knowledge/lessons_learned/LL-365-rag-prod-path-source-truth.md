# LL-365: RAG production path source labels must match runtime

**Severity**: HIGH  
**Date**: 2026-08-04  
**Tags**: `rag`, `webhook`, `defended`, `honesty`

## What happened

Docs and webhook still claimed LanceDB-first while `LessonsLearnedRAG.query` defaulted to
defended `retrieve_for_trade`. Response headers could mislabel retrieval source.

## Prevention

1. Source-aware response headers (`defended` | `pipeline` | `lancedb` | `keyword`).
2. RAGSafetyGuard queries put-credit by default (not iron condor).
3. Scorecard separates architecture A+, lab holdout A+, stretch A+, trading edge.
4. Re-run `evaluate_rag.py` after retrieval changes; never invent metrics.

## Sensitivity

operator
