---
name: supermemory
description: >
  Official SuperMemory adapter for the trading lab. Bearer SUPERMEMORY_API_KEY,
  POST /v3/documents, POST /v4/search, singular containerTag trading-lab.
  Local ledgers remain edge truth. Use when SuperMemory, console.supermemory.ai,
  container tags, or memory vs RAG comes up in this repo.
---

# SuperMemory (trading)

Official product: [console.supermemory.ai](https://console.supermemory.ai)
(Google SSO `iganapolsky@gmail.com`). Docs: [supermemory.ai/docs](https://supermemory.ai/docs).

```bash
python scripts/supermemory_ops.py status
python scripts/supermemory_ops.py search "why is inventory unclean?"
python scripts/supermemory_ops.py ingest-lessons
make supermemory-check
```

## Hard rules

- Tenant is `trading-lab`. Never `secure-yolo`.
- Do not treat SuperMemory hits as P/L, expectancy, or profit factor.
- Do not dump `rag_knowledge/arxiv/`.
- Do not clone the console memory-graph UI.
- CI must pass without a live key.
