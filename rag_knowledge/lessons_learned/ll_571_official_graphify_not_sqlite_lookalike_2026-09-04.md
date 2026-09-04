# LL-571: Graphify means Graphify-Labs/graphify, not a SQLite dump

**Date:** 2026-09-04

**Severity:** HIGH (4)

**Category:** retrieval, knowledge graph, official contract

## What happened

Untracked local scripts (`setup_graphify_integration.py`, `integrate_graphify.py`) treated Graphify as `pip install graphify` / `python -m graphify .` and dumped nodes into `financial_graph.sqlite`. That is not [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify).

Official contract:

- PyPI package is **`graphifyy`**. CLI is **`graphify`**.
- Install: `uv tool install graphifyy`.
- Retrieval: `graphify query|path|explain` against `graphify-out/graph.json`.
- Edges are `EXTRACTED` / `INFERRED` / `AMBIGUOUS`.
- `graph.html` is visualization, not retrieval.
- `graphify-out/` stays gitignored (LL-349).
- Financial Graph RAG (`src/rag/graph`) stays the trading-domain graph.

## Prevention

- `scripts/graphify_ops.py` + `src/rag/graphify/` wrap the official CLI and graph.json.
- Tests fail if adapter sources contain `pip install graphify`, `python -m graphify .`, or SQLite `graphify_nodes`.
- `make graphify-check` is part of `make check`.

## Verification

Run `python scripts/graphify_ops.py status --json` and `pytest tests/test_graphify_contract.py`.
