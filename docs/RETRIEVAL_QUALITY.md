# Retrieval quality — ranked levers (trading RAG)

**Goal:** higher Precision@5 / Recall@5 / MRR / lower OOD FPR on lessons used as safety memory — not marketing.

Production path: `TradingRAGPipeline.search()` uses `QualityRetriever` when `RAG_QUALITY_STACK=1` (default).

## Ranked improvement order (ROI for this corpus)

1. **Hybrid BM25/FTS + dense + RRF** — keyword-heavy lessons (LL-ids, "200% stop") and semantic neighbors. FTS hybrid live; vector via `RAG_USE_VECTOR=1`.
2. **Reranking** — top-20 candidates to top-5 safety-relevant (CE when available; domain keyword fallback).
3. **Query rewrite + multi-query** — short agent questions expanded with trading synonyms.
4. **Parent-child retrieval** — match section chunk, return full lesson so Prevention stays intact.
5. **Metadata + filtering** — severity / strategy / ticker cuts false positives (fail-open if filter empties).
6. **Header-aware chunking** — split on markdown headers; keep rule blocks whole.
7. **Better embeddings** — optional BGE/e5 (`sentence-transformers`); never a hard import.

## What not to do first

- More frameworks (LangChain) without eval gates
- Giant chunks that bury CRITICAL prevention
- Filters so hard empty results silently approve risk (use safety gate modes)

## Eval loop

```bash
python3 scripts/evaluate_rag.py
```

Targets (process): P@5 >= 0.40, R@5 >= 0.60, OOD FPR <= 0.20.

## Env knobs

- `RAG_QUALITY_STACK` default `1` — QualityRetriever on search path
- `RAG_USE_VECTOR` default `0` — dense path when embedder/index available
- `TRADING_RAG_DB` default `.claude/memory/rag_pipeline.db` — FTS5 store

## Credential store enforcement (related ops)

Global Grok hook: `~/.grok/hooks/credential-store-enforce.json`

On `UserPromptSubmit`, credential-like pastes inject a hard store+skill instruction and write receipts under `~/.hermes/receipts/credential-store-enforce/`.
