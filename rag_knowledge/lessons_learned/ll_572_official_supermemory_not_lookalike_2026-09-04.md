# LL-572: SuperMemory means official v3/v4, not a memories.create dump

**Date:** 2026-09-04

**Severity:** HIGH (4)

**Category:** retrieval, memory, official contract

## What happened

An untracked local script (`scripts/integrate_supermemory.py`) treated SuperMemory
as `from supermemory import Client` plus `client.memories.create` with a tags
list, then dumped lessons and `financial_graph.sqlite`. That is not the product
on [console.supermemory.ai](https://console.supermemory.ai).

Official contract (docs 2026-07/09, live console Max Smith KDP LLC Free):

- Auth: `Authorization: Bearer $SUPERMEMORY_API_KEY`
- Write: `POST https://api.supermemory.ai/v3/documents`
- Search: `POST https://api.supermemory.ai/v4/search` with singular `containerTag`
- Python SDK: `from supermemory import Supermemory` / `client.add` /
  `client.search.memories`
- `searchMode`: `memories` | `documents` | `hybrid` (hybrid for operator context)
- Trading tenant: `trading-lab`. Live org also has `secure-yolo` — do not mix.
- Local `data/trades.json` / FTS lessons remain edge truth.

## Prevention

- `scripts/supermemory_ops.py` + `src/rag/supermemory/` wrap stdlib HTTP.
- Tests fail if adapter sources contain the wrong SDK class, memories-create RPC,
  `x-api-key`, or SQLite dump.
- `make supermemory-check` is part of `make check`.
- Ingest is bounded curated lessons (`taskType=superrag`). No arXiv dump.

## Verification

Run `python scripts/supermemory_ops.py status` and
`pytest tests/test_supermemory_contract.py`.
