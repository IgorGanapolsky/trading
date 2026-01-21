# LL-268: RAG Testing Evaluation - Retrieval Accuracy and Grounding

**ID**: LL-268
**Date**: 2026-01-21
**Severity**: HIGH
**Category**: Testing

## Summary
Evaluated Medium article "RAG Testing — Validating Retrieval Accuracy, Grounding, and Context Leakage" by Gunashekar R (Jan 2026). **Verdict: VALUABLE** — addresses critical gap in our RAG testing.

## Key Findings

### What We're Missing
| Testing Area | Current State | Risk |
|--------------|---------------|------|
| Retrieval Accuracy | ❌ No Precision@k, Recall@k, MRR, nDCG metrics | RAG could return irrelevant lessons |
| Grounding/Faithfulness | ❌ No checks | Generated advice may hallucinate |
| Context Leakage | ❌ No tests | Sensitive data could be exposed |
| Regression Testing | ❌ No golden set | RAG degradation goes undetected |

### What We Already Have (No Changes Needed)
- Vertex AI RAG with text-embedding-004 (768-dim)
- Hybrid search (semantic + keyword)
- TF-IDF local fallback
- Basic smoke tests for imports

## Decision
**IMPLEMENT** basic RAG evaluation tests:
1. Add RAGAS framework to requirements.txt
2. Create golden test set (10-20 query-answer pairs)
3. Weekly CI evaluation job

## Implementation Priority
**Medium** — Important for reliability but not blocking trading operations.

## Key Metrics to Track
- Precision@5: Are retrieved docs relevant?
- Faithfulness: Is output grounded in context?
- Hallucination Rate: Track unsupported claims

## Sources
- [RAG Evaluation 2026 Metrics](https://labelyourdata.com/articles/llm-fine-tuning/rag-evaluation)
- [RAGAS Framework](https://arxiv.org/abs/2309.15217)
- [Evidently AI RAG Guide](https://www.evidentlyai.com/llm-guide/rag-evaluation)

## Tags
rag, testing, evaluation, retrieval, grounding, vertex-ai, valuable
