# Trading RAG quality scorecard (AGENT-70 A+ platform)

**Updated:** 2026-08-04  
**Scope:** Paper SPY put-credit lab — not multi-tenant SaaS, not live HFT.

**Honesty:** Architecture A+ (capability matrix + `verify_rag_aplus.py`) is **not** the same
as measured holdout A+ (`scripts/evaluate_rag.py`) or trading edge (n≥30 paired closes).
Webhook/LessonsLearnedRAG default to **defended** retrieval; LanceDB is fallback only.
Re-run evaluate_rag after retrieval changes; do not copy stale bake-off numbers.

## Measured holdout (lab eval) (fresh 2026-08-04, tip of main worktree)

Re-run: `python scripts/evaluate_rag.py` on 10 default queries, k=5, ~174 lessons.

| Metric                   |      Value | Lab A+ gate |    Stretch |
| ------------------------ | ---------: | ----------: | ---------: |
| Precision@5              | **0.5600** |  ≥0.40 PASS | ≥0.50 PASS |
| Recall@5                 | **0.7200** |  ≥0.60 PASS | ≥0.75 FAIL |
| MRR                      | **0.9500** |  ≥0.50 PASS | ≥0.80 PASS |
| nDCG@5                   | **0.7294** |  ≥0.55 PASS | ≥0.80 FAIL |
| Queries with ≥1 relevant |      10/10 |           — |          — |
| Graph golden             |    **5/5** |           — |          — |

**Lab grade (script gates): A+.** Stretch A+ not claimed (recall/nDCG).

RAG quality reduces preventable operational errors. It does **not** create a
trading edge and does **not** prove $1,000–$6,000/month after tax. That outcome
requires a paper-to-live cohort with positive expectancy, PF > 1, drawdown
compliance, broker reconciliation, n ≥ 30 paired closes, and filled-order evidence.

## Architecture (capability matrix) — target **A+ / 10/10**

| Capability                                                    | Status  | Owner module                                           |
| ------------------------------------------------------------- | ------- | ------------------------------------------------------ |
| Messy multi-format cascade (PDF/HTML/OCR)                     | Shipped | `src/research/messy_document_parser.py`                |
| Hierarchical + late chunking                                  | Shipped | `src/rag/chunking.py`                                  |
| Document ACL (paper vs live principals)                       | Shipped | `src/rag/acl.py`                                       |
| FTS5 seed + pragmatic hybrid + multi-query                    | Shipped | `src/rag/retrieve_for_trade.py`, `pragmatic_hybrid.py` |
| Pairwise heuristic rerank (+ opt-in CE/LLM)                   | Shipped | `src/rag/cross_encoder_rerank.py`                      |
| Parent expand for trade gates                                 | Shipped | `retrieve_for_trade._parent_expand_lessons`            |
| OOD hard-reject                                               | Shipped | `retrieve_for_trade` (`ood_min_score`)                 |
| Retrieval traces (JSONL)                                      | Shipped | `src/rag/observability.py`                             |
| Domain embedding backend (BGE opt-in / feature-hash fallback) | Shipped | `src/rag/embedding_backend.py`                         |
| Answer faithfulness / groundedness                            | Shipped | `src/rag/answer_evaluation.py`                         |
| Temporal Graph RAG + TokenGuard                               | Shipped | `src/rag/graph/*`                                      |
| TradeGateway wired (strategy family + path meta)              | Shipped | `src/risk/trade_gateway.py`                            |
| Unified platform facade                                       | Shipped | `src/rag/platform.py`                                  |
| Fail-closed verify gate                                       | Shipped | `scripts/verify_rag_aplus.py`                          |

```bash
# Architecture gates (must pass)
.venv/bin/python scripts/verify_rag_aplus.py
make rag-aplus-check

# Optional measured holdout (slower)
TRADING_RAG_RUN_HOLDOUT=1 .venv/bin/python scripts/verify_rag_aplus.py
.venv/bin/python scripts/evaluate_rag.py
```

Architecture grade is computed by `TradingRAGPlatform.scorecard()` as the fraction
of capabilities present × 10. **A+ requires ≥ 9.5 / 10 and all flags true.**

## Measured retrieval gates (holdout)

Frozen set: `tests/fixtures/rag_retrieval_holdout.json` (when present) plus
evaluator defaults in `src/rag/evaluation.py`.

| Metric           | Near-A+ (lab) | Stretch A+ |
| ---------------- | ------------: | ---------: |
| Precision@5      |        ≥ 0.40 |     ≥ 0.50 |
| Recall@5         |        ≥ 0.60 |     ≥ 0.75 |
| MRR              |        ≥ 0.50 |     ≥ 0.80 |
| nDCG@5           |        ≥ 0.55 |     ≥ 0.80 |
| Unanswerable FPR |        ≤ 0.20 |     ≤ 0.10 |
| Warm p95 latency |     ≤ 2000 ms |  ≤ 2000 ms |

`scripts/evaluate_rag.py` prints PASS/FAIL per gate and a grade line.

**Honesty rule:** Do not copy old bake-off numbers forward as current proof.
Rerun after each retrieval change. If semantic BGE is not loaded, report the
feature-hash backend explicitly — never call the fallback "semantic."

## Answer-layer gates

`RAGAnswerEvaluator` requires (default threshold 0.80):

- claim faithfulness against retrieved context
- groundedness (support + citations)
- answer relevance to the query
- rejection of unsupported profit guarantees

## Graph RAG

See `docs/GRAPH_RAG.md`. Golden path: `scripts/verify_graph_rag.py` (5/5 queries
when index is built). Graph answers are evidence, not trade authorization.

## Path from scorecard to money

1. Keep architecture A+ green (`make rag-aplus-check`).
2. Improve measured holdout toward stretch A+ with reviewed hard-negatives / domain reranker bake-off — not hand-tuning a frozen set forever.
3. Use retrieval only to enforce the active paper strategy and block known failures.
4. Complete put-credit paper cohort (n ≥ 30, expectancy > 0, PF > 1).
5. Only then evaluate bounded live capital. Proof = broker fills + reconciled P/L.

## What this PR is not

- Not a claim that holdout metrics are already stretch-A+ without a fresh run.
- Not multi-tenant SaaS ACL (single-operator principals only).
- Not permission to trade live or claim profitability.
