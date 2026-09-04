# Official SuperMemory adapter

Optional long-term memory for the trading lab. Local paired ledgers remain
edge truth. SuperMemory does not prove expectancy, profit factor, or P/L.

## Product contract

Logged-in console (Google SSO `iganapolsky@gmail.com`, org Max Smith KDP LLC,
Free): [console.supermemory.ai](https://console.supermemory.ai)

Official docs: [supermemory.ai/docs](https://supermemory.ai/docs)

| Item    | Official                                     | Lookalike (do not ship)              |
| ------- | -------------------------------------------- | ------------------------------------ |
| Auth    | `Authorization: Bearer $SUPERMEMORY_API_KEY` | `x-api-key` / `x-sm-user-id`         |
| Write   | `POST /v3/documents` (`client.add`)          | `client.memories.create`             |
| Search  | `POST /v4/search` (`client.search.memories`) | `/v3/search` as the default          |
| Tenancy | singular `containerTag`                      | `tags=[...]` / `containerTags` on v4 |
| Python  | `from supermemory import Supermemory`        | `from supermemory import Client`     |

## How this repo uses it

- Adapter: `src/rag/supermemory/` (stdlib HTTP, lazy, optional)
- CLI: `scripts/supermemory_ops.py`
- Default tenant: `trading-lab`
- Live console currently also has tenant `secure-yolo`. Trading never writes or
  searches that tag.
- Lesson ingest is bounded and curated (`taskType=superrag`). No arXiv dump.
- `searchMode=hybrid` for operator context. Edge queries stay on local ledgers.
- Memory-graph UI in the console is visualization, not retrieval.

```bash
python scripts/supermemory_ops.py status
python scripts/supermemory_ops.py search "why is iron condor killed?"
python scripts/supermemory_ops.py ingest-lessons
# live POST only when SUPERMEMORY_API_KEY is set:
python scripts/supermemory_ops.py ingest-lessons --live
make supermemory-check
```

CI does not require a live key. Network tests are opt-in.

`pytest tests/test_supermemory_contract.py` is the prevention gate. Do not dual-edit
`Makefile`, `docs/EXTENSIONS.md`, or `skills/trading-ops/SKILL.md` while AGENT-571
holds those files.
