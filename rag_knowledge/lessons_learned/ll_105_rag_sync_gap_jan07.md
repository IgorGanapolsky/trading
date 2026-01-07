# Lesson Learned #105: Post-Trade RAG Sync Was Missing

**Date**: January 7, 2026
**Severity**: HIGH
**Category**: `data-integrity`, `observability`, `mandate-violation`

## What Happened

During CEO review on Jan 6, 2026, we discovered that trades were NOT being recorded to Vertex AI RAG or ChromaDB after execution. The pre-session RAG check existed, but NO post-session sync was implemented.

This violated the CLAUDE.md mandate:
> "Record every trade and lesson in BOTH ChromaDB AND Vertex AI RAG (MANDATORY)"

## Root Cause

- Pre-session RAG check was implemented (reads lessons before trading)
- Post-session RAG sync was NEVER implemented (writes trades after trading)
- JSON backup was working, but not synced to vector databases
- CEO could not query trades via Dialogflow because data wasn't in Vertex AI

## Impact

- Trades from Jan 3-6, 2026 were NOT in RAG databases
- Dialogflow queries for trade history returned nothing
- Learning loop was broken (can't learn from trades not recorded)
- Violated CLAUDE.md mandate

## Resolution

1. Created `scripts/sync_trades_to_rag.py` - syncs trades to both Vertex AI and ChromaDB
2. Added "Sync Trades to RAG (Post-Execution)" step to daily-trading.yml
3. Step runs after every trade session, with graceful fallback to JSON

## Prevention

- Always verify BOTH pre-flight AND post-flight steps exist for any critical flow
- Test end-to-end data flow: execute trade → record to JSON → sync to RAG → query via Dialogflow
- Add monitoring for RAG corpus size vs JSON trade count

## Tags

`rag`, `vertex-ai`, `chromadb`, `data-sync`, `post-execution`, `mandate-compliance`
