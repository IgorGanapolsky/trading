# Graph RAG for the trading lab

**Status:** production-ready local foundation (paper SPY put-credit scope)  
**Linear:** AGENT-70  
**Code:** `src/rag/graph/` · **CLI:** `scripts/graph_rag_query.py`

## Why not plain vector RAG?

Flat embeddings retrieve similar _text_, but this lab’s decisions depend on
**relationships**: kill-switch → strategy succession, critical lessons →
prevention edges, paired trades → strategy outcomes, VIX/Fed concepts → SPY.
Graph RAG encodes those edges with **temporal validity** so history is
preserved when rules change.

## Stack choice (deliberate)

| Industry option      | Fit for this repo             | Decision                                                            |
| -------------------- | ----------------------------- | ------------------------------------------------------------------- |
| Graphiti + Neo4j     | Real-time news temporal graph | **Later optional** — ops heavy for paper cohort                     |
| FalkorDB             | Sub-140ms quant traversal     | **Not required** — our latency budget is research/session, not HFT  |
| LightRAG             | Dual-level macro↔micro        | Pattern adopted in router + multi-hop BFS                           |
| TypeGraph / Postgres | Lean startup                  | **Closest** — we use **SQLite property graph** (stdlib, offline CI) |

**Primary store:** `data/rag/financial_graph.sqlite` (gitignored runtime artifact; rebuild from ledgers).  
**Vector fusion:** optional `LessonsLearnedRAG` / LanceDB when installed.  
**No hard deps** beyond the Python stdlib for import and CI.

## Ontology (hybrid graph)

```text
[MACRO_EVENT: IC kill] --KILLED--> [STRATEGY: iron_condor]
        |
     SUCCEEDS
        v
[STRATEGY: spy_put_credit] <--GOVERNS-- [RULE: stop 200% / 25% TP / 7 DTE]
        ^
   PREVENTS / RELATED_TO
        |
[LESSON: LL-*] --MENTIONS--> [TICKER: SPY]
        |
   OUTCOME_OF
        |
[TRADE: paired structure] --MENTIONS--> [TICKER: SPY]

[CONCEPT: vix_spike] --IMPACTS--> [STRATEGY: spy_put_credit]
[SIGNAL: runtime JSON] --IMPACTS--> [TICKER: SPY]
```

### Node types

`ticker`, `strategy`, `lesson`, `trade`, `rule`, `macro_event`, `regime`,
`signal`, `sector`, `concept`

### Edge types (temporal)

`MENTIONS`, `IMPACTS`, `CORRELATES_WITH`, `CAUSED_BY`, `PREVENTS`, `KILLED`,
`SUCCEEDS`, `ANCHORS`, `BLOCKS`, `CONTAINS`, `RELATED_TO`, `OUTCOME_OF`,
`GOVERNS`, `TRADES`

Edges carry `valid_from` / `valid_to` (NULL `valid_to` = still active).

## Multi-agent workflow (deterministic)

```text
User / strategy query
        │
        ▼
1. ROUTING  (src/rag/graph/router.py)
   intent: strategy_status | lesson_risk | trade_evidence | macro_impact | hybrid
        │
        ▼
2. RETRIEVAL FUSION  (retriever.py)
   graph BFS (1–3 hops) + optional lesson vector hits
        │
        ▼
3. TOKENGUARD  (token_gateway.py)
   soft budget (default 1800 tok) · hard halt (3200)
        │
        ▼
4. CONTEXT PACK  (pipeline.py)
   ready for Hermes/Claude — never auto-submits orders
```

## Operator commands

```bash
# Full rebuild from kill switch + lessons + trades + runtime signals
python scripts/graph_rag_query.py --rebuild

# Stats
python scripts/graph_rag_query.py --stats

# Query (hybrid)
python scripts/graph_rag_query.py --query "why is iron condor killed?"

# Graph-only (no LanceDB/lesson fusion)
python scripts/graph_rag_query.py --query "put credit stop loss" --graph-only

# Machine-readable
python scripts/graph_rag_query.py --query "vix impact on SPY" --json
```

## Programmatic API

```python
from src.rag.graph import get_graph_rag_pipeline

pipe = get_graph_rag_pipeline()
result = pipe.query("why is live capital blocked?")
assert result.allowed
print(result.context)
```

## What this is _not_

- Not a live alpha generator and not permission to open risk.
- Not a substitute for `data/trades.json` paired evidence.
- Not Neo4j/FalkorDB production clustering (can be added as an optional adapter later).
- Does not claim put-credit profitability; graph trade nodes are evidence leaves only.

## Evaluation posture

Before trusting Graph RAG in any agent loop that influences risk:

1. Rebuild graph after kill-switch or large lesson ingest.
2. Spot-check strategy_status queries return `KILLED` / `SUCCEEDS` paths.
3. Run `pytest tests/test_graph_rag.py`.
4. Keep TokenGuard hard limits on; multi-hop without a budget burns tokens.

## Future upgrades (optional)

1. **Graphiti adapter** — stream news/X into temporal edges when news ingest is in scope.
2. **Timescale/Lance candlestick anchors** — `ANCHORS` edges from structure nodes to bar embeddings.
3. **RAGAS offline suite** — graded graph path accuracy vs golden multi-hop queries.
4. **FalkorDB backend** — only if measured P99 on SQLite BFS fails a real latency SLO.
