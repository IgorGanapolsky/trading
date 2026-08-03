# Production RAG architecture and defended grade

## Verdict

The implementation is now a coherent, production-shaped RAG service rather
than several disconnected search helpers. Its **code and deterministic
retrieval evaluation grade is A / 9.2**. The default dependency-light path is
still a **B / 7.8** because it uses `hashing-v1` and heuristic reranking.
Production mode uses strict-quality indexing: governed lessons are active and
legacy failures are explicitly quarantined instead of silently diluting the
index. It is not A+ until the semantic runtime and deployment SLOs are proven
outside this development machine.

Current deterministic holdout at `k=5`:

| Metric                  | Result |   Gate |
| ----------------------- | -----: | -----: |
| Precision@5             | 0.7600 | ≥ 0.70 |
| Recall@5                | 0.9183 | ≥ 0.85 |
| MRR                     | 1.0000 | ≥ 0.95 |
| nDCG@5                  | 0.9301 | ≥ 0.90 |
| OOD accuracy            | 1.0000 |   1.00 |
| OOD false-positive rate | 0.0000 |   0.00 |

These scores measure retrieval on a small checked-in golden set. They do not
measure trading profitability and cannot open the live-capital gate.

## End-to-end data flow

```text
👎 event / reviewed markdown
  → Unicode normalization + secret redaction + size validation
  → schema quality gate (severity, actionable prevention, minimum context)
  → parse metadata + section-aware chunks + stable content hash
  → transactional SQLite document store + FTS5 chunk index
  → idempotent insert/update/tombstone and cache invalidation

query + metadata filters
  → child-chunk BM25 candidates + dense candidates + reciprocal-rank fusion
  → lexical bigram/unigram, phrase, title, and exact metadata signals
  → multi-query expansion only when top lexical confidence < 0.6
  → cross-encoder, validated LLM, or explicitly degraded heuristic rerank children
  → OOD rejection + bounded parent-section expansion + document diversification
  → bounded, cited, injection-marked context
  → deterministic high-risk tool gate
```

## Architecture decisions

### Chunking

Lessons are short operational documents, so fixed token windows alone would
separate failures from their prevention. The pipeline first splits on Markdown
sections, then applies bounded overlapping windows to oversized sections.
Chunks retain the parent lesson ID, heading, sequence, content hash, severity,
tags, source, source path, version, and quality status.

Trade-off: overlap costs index space, but it reduces boundary misses. Retrieval
keeps child chunks distinct through fusion and reranking, then expands a winning
child to its bounded parent section. This preserves precise chunk citations
without starving the generator of surrounding qualifications. Repeated parent
sections are deduplicated and no document contributes more than one final
section in a result set.

### Embeddings

The intended local semantic model is `BAAI/bge-small-en-v1.5`: small enough for
CPU deployment and strong enough for short English retrieval. Model loading is
offline by default; production images must pre-cache the artifact. If the model
is unavailable, deterministic hashing keeps search operational but marks health
as degraded. `RAG_REQUIRE_SEMANTIC=1` turns that degradation into failed
readiness.

The hashing fallback is availability insurance, not an equivalent embedding
model and never qualifies as A+ production evidence.

### Vector and lexical storage

SQLite is the authoritative local store because the corpus is small, updates
must be transactional, FTS5 is fast, and the system needs a dependency-light
recovery path. Dense vectors are an acceleration/relevance layer, not the
source of truth. The design avoids a remote vector service's network latency,
cost, and availability dependency at the current corpus size.

If the corpus grows into millions of chunks or requires multi-node writes, move
the dense index to a managed/vector-native store while keeping content hashes,
versions, tombstones, and the evaluation contract stable.

### Hybrid rather than pure vector

Trading lessons contain exact identifiers, option symbols, error messages, and
policy terms that lexical search handles better than semantic similarity.
Vector search recovers paraphrases. The pipeline therefore uses reciprocal-rank
fusion to combine chunk-level BM25 and dense ranks, then scores
bigram-Jaccard, unigram coverage, phrase/title signals, and dense similarity.
Rank fusion is more stable than assuming BM25 and cosine scores share a
calibrated scale. Metadata filters run before either retrieval backend.

Pure vector search was rejected because it can blur exact risk-policy language;
pure keyword search was rejected because it misses paraphrased incidents.

### Metadata schema

Required fields are:

- stable `lesson_id`, title, severity, prevention, tags, and source;
- `source_path`, created/updated timestamps, content SHA-256, and version;
- chunk heading and ordinal;
- quality-gate status, redaction count, and tombstone state.

Exact severity, source, whole-tag, section, and minimum-version filters are
validated and applied to BM25 and vector candidates before ranking. Whole-tag
matching prevents a filter such as `risk` from accidentally matching
`risk-adjusted`.

This supports deterministic filters, provenance, idempotent updates, deletion,
audits, and exact citation assembly.

### Updates and freshness

Ingestion computes stable hashes. Unchanged documents do not rewrite chunks;
changed documents atomically replace the active version; missing documents can
be tombstoned during an explicit delete-missing sync. Successful ingestion is
recorded with discovered/inserted/updated/unchanged/deleted/rejected counts,
duration, and errors. Query caches include the index generation and are
invalidated after writes.

## Retrieval and gating

Candidate generation is wide, child-chunk-level, filter-first, and hybrid. Conditional
multi-query expansion is limited to three deterministic variants and fires
only when the best lexical score is below 0.6, controlling latency and query
drift. Rerankers receive unique child chunk IDs and must return only those
candidate IDs; unknown or duplicate IDs are discarded. Only after reranking is
the winning child expanded to its parent section and diversified by document.

The cross-encoder is the preferred local reranker. A structured LLM reranker is
allowed only when configured and its JSON output passes ID validation. The
heuristic path is deterministic and available during dependency/provider
failure, but health reports it as degraded.

Context assembly enforces a character budget, escapes instructions found in
retrieved text, separates data from system instructions, and includes lesson
IDs and source paths. The final tool decision is deterministic and fails closed
for a high-risk tool when the index is not ready or relevant severe prevention
evidence crosses reviewed thresholds.

## Service and production concerns

`src/rag/service.py` provides authenticated, schema-validated FastAPI endpoints
for search, feedback, gating, reindexing, health, readiness, and Prometheus
metrics. Blocking model/SQLite work runs off the event loop. Admin mutations
require the admin token; comparison uses constant-time checks.

Primary failure modes and controls:

| Failure mode                              | Control                                                        |
| ----------------------------------------- | -------------------------------------------------------------- |
| embedding/reranker model absent           | explicit degraded health; semantic-required readiness fails    |
| malformed or secret-bearing feedback      | normalization, redaction, schema/size gate                     |
| partial update or duplicate event         | SQLite transaction, stable event/content hash, versioning      |
| deleted source remains retrievable        | explicit tombstone sync                                        |
| LLM reranker hallucinates IDs             | strict structured output and candidate-ID validation           |
| irrelevant query returns confident lesson | OOD threshold and unanswerable holdout                         |
| retrieved prompt injection                | untrusted-data boundary and bounded cited assembly             |
| stale index or failing database           | ingestion timestamps, integrity/FTS checks, readiness failure  |
| provider latency/cost spike               | local models, conditional expansion, cache, fallback telemetry |

Observed fresh-local fallback benchmark on 172 documents / 1,683 chunks:

- ingestion: about 459 ms;
- cold-query median: about 105 ms, observed range 41–318 ms;
- 105-query mixed run: p50 0.083 ms, p95 0.606 ms, p99 134.665 ms with
  100 cache hits.

The strict semantic proof used 135 governed documents, BGE embeddings, and the
cross-encoder. Its checked-in holdout remained above every retrieval gate. A
representative warmed run measured p50 122 ms and p95 276 ms. Repeated CPU
model/index warmups ranged from roughly 14 to 90 seconds; readiness remained
closed until they completed.

These are development-machine measurements, not production SLO proof. The
recommended initial SLOs are p95 search below 300 ms with local models, error
rate below 0.5%, zero unauthorized admin writes, and index freshness below five
minutes after an accepted event.

## Evaluation loop

The checked-in golden set measures Precision@k, Recall@k, MRR, nDCG, utility,
and unanswerable/OOD behavior. Tests also cover idempotent capture, update and
delete semantics, filters, conditional expansion, reranker ID validation,
context boundaries, concurrency, cache metrics, service auth, and fail-closed
gates.

To avoid optimizing against ten familiar questions forever, the next
evaluation layer should add:

1. at least 100 adjudicated incident queries split by time and strategy regime;
2. hard negatives and mutations of tool names, symbols, severities, and dates;
3. shadow retrieval logs with operator relevance labels;
4. per-slice metrics for exact identifiers, paraphrases, recency, and OOD;
5. candidate-vs-current paired significance and latency/cost regression gates.

## What remains for A+ / 10 out of 10

- review or migrate the remaining quarantined legacy lessons when their
  historical context is still valuable;
- package and pre-cache both semantic models in the production image;
- run with `RAG_REQUIRE_SEMANTIC=1` and prove non-degraded readiness;
- expand the adjudicated holdout and add drift/canary monitoring;
- prove deployed p50/p95/p99 latency, availability, backup/restore, and alerts;
- bind every high-risk trading tool to the single deterministic gate and audit
  every allow/block decision.

The correct current outcome is strong retrieval engineering with an explicit
deployment gap—not a ceremonial A+ label.
