# LL-642 — CobbleDB FORMAT: durable state vs batched hot reads

Source: [Perplexity CobbleDB](https://www.perplexity.ai/hub/blog/cobbledb) (2026-09-14)

## Steal (FORMAT)

1. **Split write and read.** Durable document state (markdown lessons) is not the query path.
2. **Batch exports.** A Lorry-style export writes prepared records; query does batched get-by-key.
3. **Omit features we do not need.** No transactions, no replica sync, no RocksDB. Short ingest lag is acceptable.
4. **Honesty.** Their 5x latency / 20% DynamoDB figures are _their_ observational before-and-after, not ours.

## Do not

- Clone CobbleDB, Pillar, Lorry, YTsaurus, or DynamoDB.
- Glob `rag_knowledge/**/*.md` on every lesson query when a hot JSONL exists.
- Claim 5× faster or 20% cheaper for this lab.

## Ship

`scripts/cobble_hot_path.py` export|query|get|status. Tests prove query/get work after durable files are deleted.

ThumbGate already has `npx thumbgate cobble-hot-store-split` (`/cobble-hot-store-compare-not-clone`). This file is the **trading lesson-rail analog**, not a second database.

## Cash

Ops/eval only. Commercial fee-yes remains separate.
