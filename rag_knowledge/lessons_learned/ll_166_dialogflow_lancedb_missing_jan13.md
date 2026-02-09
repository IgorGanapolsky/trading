# LL-166: Dialogflow Webhook Missing LanceDB - Only Local Keyword Search

**ID**: ll_166_dialogflow_lancedb_missing_jan13
**Date**: 2026-01-13
**Severity**: HIGH

## Problem

Dialogflow webhook was falling back to local keyword search instead of using LanceDB semantic search. CEO saw "Based on our lessons learned (local search):" instead of synthesized answers from the LLM.

## Root Cause

1. **Dockerfile.webhook** explicitly excluded LanceDB:
   - No `lancedb` or `sentence-transformers` packages
   - Did NOT copy document-aware RAG module

2. **Index not built** at deploy time:
   - LanceDB tables missing, so semantic retrieval returned empty results

## Fix

1. Updated Dockerfile.webhook:
   - Added `lancedb` + embeddings dependencies
   - Copied document-aware RAG module

2. Enforced index build:
   - Auto-index on startup (`LANCEDB_AUTO_INDEX=true`)

## Impact

- Dialogflow was useless for answering CEO questions
- Only dumped keyword-matched lessons instead of synthesizing answers
- No semantic search capability despite LanceDB being available

## Prevention

1. Always verify Cloud Run environment variables after deployment
2. Test Dialogflow responses show "LanceDB RAG" not "local search"
3. Include LanceDB deps in Dockerfile when semantic search is required

## Tags

dialogflow, lancedb, rag, cloud-run, deployment, semantic-search
