# Trading defended RAG pipeline

**Native to this repo** (not ThumbGate). Enabled by default via `TRADING_RAG_DEFENDED=true`.

## Pipeline

```text
thumbs-down capture -> normalize + quality-gate -> store lesson (SQLite FTS5 + optional markdown)
  -> retrieve: FTS5 seed + keyword + char bigram-Jaccard (pragmatic hybrid + RRF)
  -> multi-query: up to 3 variants when top lexical < 0.6
  -> rerank: pairwise heuristic CE (optional LLM listwise if API key present)
  -> assemble context -> TradeGateway / TradeVerifier gate (deterministic)
```

## Modules

| Stage                  | Module                                                                   |
| ---------------------- | ------------------------------------------------------------------------ |
| Capture / quality-gate | `src/rag/feedback_quality.py`, `scripts/capture_trading_feedback.py`     |
| Store (FTS5)           | `src/rag/lesson_store.py`, `scripts/sync_lessons_to_sqlite_fts.py`       |
| Hybrid retrieve        | `src/rag/pragmatic_hybrid.py`                                            |
| Multi-query            | `build_query_variants` + `resolve_query_plan` in `retrieve_for_trade.py` |
| Rerank                 | `src/rag/cross_encoder_rerank.py`                                        |
| Unified API            | `src/rag/retrieve_for_trade.py`                                          |
| Trade gate             | `src/risk/trade_gateway.py` CHECK 12, `src/rag/trade_verifier.py`        |
| Default query path     | `LessonsLearnedRAG.query()` prefers defended                             |

## Operator commands

```bash
# Backfill markdown lessons -> FTS5
python scripts/sync_lessons_to_sqlite_fts.py --force

# Capture a structured thumbs-down as a lesson
python scripts/capture_trading_feedback.py --signal negative \
  --context "SPY put credit entry" \
  --what-went-wrong "Opened multi-lot against 1-lot rule" \
  --what-to-change "Enforce MAX_LOT_SIZE=1 before submit"

# Query (Python)
python -c "from src.rag.retrieve_for_trade import retrieve_for_trade as r; print(r('iron condor exit').lessons[:3])"

# Eval
python scripts/evaluate_rag.py --verbose
```

## Env

| Var                           | Default | Meaning                                          |
| ----------------------------- | ------- | ------------------------------------------------ |
| `TRADING_RAG_DEFENDED`        | `true`  | Use FTS5+hybrid+CE path in `LessonsLearnedRAG`   |
| `TRADING_RAG_SKIP_FTS_ENSURE` | unset   | Skip auto-backfill on first query                |
| `LANCEDB_RAG`                 | `true`  | Legacy vector path (used only if defended fails) |

## A+ quality gates (measured)

Run:

```bash
python scripts/evaluate_rag.py --k 5 --include-unanswerable
```

**Targets (all required for grade A+):**

| Gate                    | Target |
| ----------------------- | ------ |
| Precision@5             | ≥ 0.40 |
| Recall@5                | ≥ 0.60 |
| MRR                     | ≥ 0.50 |
| nDCG@5                  | ≥ 0.55 |
| Unanswerable accuracy   | ≥ 0.80 |
| OOD false-positive rate | ≤ 0.20 |

**Evidence (AGENT-40, 2026-08-03, 172 lessons, offline heuristic CE):**

| Metric       | Value    |
| ------------ | -------- |
| P@5          | **0.56** |
| R@5          | **0.72** |
| MRR          | **0.95** |
| nDCG@5       | **0.75** |
| OOD accuracy | **1.00** |
| OOD FPR      | **0.00** |

OOD rejection is hard: non-trading queries return **empty** from `retrieve_for_trade`, and `LessonsLearnedRAG.query()` does **not** fall through to keyword search on empty defended results (that fallthrough caused 67% FPR).

Gold lesson IDs are **corpus-aligned** (stale renamed lessons were removed from the eval set).

## Tests

```bash
pytest tests/test_retrieve_for_trade.py tests/test_lessons_learned_rag_smoke.py -q
```

## Honest scope

World-class RAG improves **operator memory and safety context**. It does **not** by itself produce $1k/mo after-tax profit. Edge still requires put-credit cohort gates (n≥30, expectancy>0, PF>1) on paper before live capital.
