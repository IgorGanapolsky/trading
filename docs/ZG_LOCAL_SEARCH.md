# zg-style local-first search (AGENT-577)

Process steal from [Qwen zg / zvec-grep](https://github.com/zvec-ai/zvec-grep)
(MarkTechPost 2026-09-02). **We do not vendor `@zvec/zvec-grep`.** The transferable
mechanics map onto existing trading RAG rails (`UnifiedSearch`, LanceDB lessons,
ripgrep, `HybridRAGRetriever` RRF).

## What transferred

| zg mechanic                        | Trading implementation                                             |
| ---------------------------------- | ------------------------------------------------------------------ |
| Four routes behind one interface   | `hybrid` / `fts` / `vector` / `rg` in `src/rag/zg_local_search.py` |
| Default hybrid + RRF fusion        | `HybridRAGRetriever.rrf_merge` + `rrf_merge_multi`                 |
| Managed ripgrep without an index   | `ZgLocalSearch._run_rg` via system `rg`                            |
| Compact path:line evidence         | `EvidenceHit.compact_line()` / CLI default output                  |
| Local-first (no remote embeddings) | Vector route is optional local LanceDB only                        |
| Wire dead RRF into production      | `LessonsLearnedRAG.query` fuses vector+keyword when both hit       |

## What did **not** transfer

- npm `@zvec/zvec-grep` / Node 22 MCP installer
- Remote Qwen embedding auth grants
- Workspace `.zvec-grep/` index format
- Multimodal / image indexing

## Operator / agent usage

```bash
# Status
.venv/bin/python scripts/zg_search.py --check-ready

# Default hybrid (FTS + vector RRF; rg fused for symbol-like queries)
.venv/bin/python scripts/zg_search.py "put credit stop loss rules"
.venv/bin/python scripts/zg_search.py --route fts "expectancy kill criteria"
.venv/bin/python scripts/zg_search.py --route vector "iron condor exit"
.venv/bin/python scripts/zg_search.py --route rg "TradeGateway"
.venv/bin/python scripts/zg_search.py --json --limit 5 "UNCLEAN_INVENTORY"
```

## Prevention

`tests/test_zg_local_search.py` covers RRF overlap preference, injected FTS/vector
routes, live `rg` route, compact evidence, and `LessonsLearnedRAG` `hybrid_rrf`
wiring so the retriever cannot silently go unused again.
