---
layout: post
title: "---"
date: 2026-01-07
---

---
layout: post
title: "Lesson Learned #109: Bidirectional Vertex AI RAG Learning System"
date: 2026-01-07
---

# Lesson Learned #109: Bidirectional Vertex AI RAG Learning System

**ID**: LL-109
**Date**: January 7, 2026
**Severity**: HIGH
**Category**: RAG, Architecture, Learning

## The Issue

We were only WRITING to Vertex AI RAG (post-trade sync), but NEVER READING from it before trades. This violated the CEO directive: "We are supposed to be LEARNING from Vertex AI RAG!"

### Evidence

```
Previous Architecture (One-Way):
┌─────────────┐    WRITE    ┌─────────────┐
│   Trading   │ ──────────► │  Vertex AI  │
│   System    │             │     RAG     │
└─────────────┘             └─────────────┘
       ▲                           │
       │    NO READ CONNECTION!    │
       └───────────────────────────┘
```

### Root Cause

1. `sync_trades_to_rag.py` only synced AFTER trades
2. No pre-trade RAG query existed
3. Sandbox SSL blocked direct Vertex AI access
4. We assumed local TF-IDF search was "RAG learning" - it wasn't using cloud data

## The Solution

Created a **bidirectional learning system** with pre-trade RAG queries via CI:

```
New Architecture (Bidirectional):
┌─────────────┐    READ     ┌─────────────┐
│  Pre-Trade  │ ◄────────── │  Vertex AI  │
│   Check     │             │     RAG     │
└─────────────┘             └─────────────┘
       │                           ▲
       ▼                           │
┌─────────────┐    WRITE    ┌─────────────┐
│   Trading   │ ──────────► │  Post-Trade │
│   Execution │             │    Sync     │
└─────────────┘             └─────────────┘
```

## Implementation Details

### New Files Created

1. **`scripts/query_vertex_rag.py`** - Queries Vertex AI RAG before trading
   - Gets general trading advice
   - Gets symbol-specific lessons
   - Gets risk warnings
   - Gets recent lessons learned

2. **`.github/workflows/vertex-rag-pretrade.yml`** - Standalone workflow for RAG queries
   - Can be called via `workflow_call`
   - Has manual `workflow_dispatch` trigger
   - Outputs warnings for critical issues

3. **Updated `daily-trading.yml`** - Added `pretrade-rag-query` job
   - Runs BEFORE `execute-trading`
   - Uses Gemini 2.0 Flash for grounded generation
   - Saves advice to `data/rag_pretrade_advice.json`

### 2026 Best Practices Applied

Based on research from Google Cloud documentation (Jan 2026):

1. **Gemini 2.0 Flash** - Now GA for grounded answer generation
2. **Hybrid Search** - Semantic + keyword search with re-ranking
3. **Check Grounding API** - Validates responses against facts
4. **Query-First Decision Making** - Retrieve before generating

### Workflow Order

```
validate-and-test
       │
       ▼
pretrade-rag-query  ◄── NEW! Queries Vertex AI RAG
       │
       ▼
execute-trading     ◄── Uses RAG advice
       │
       ▼
sync-trades-to-rag  ◄── Writes back to RAG (existing)
```

## Key Queries Used

```python
# General trading lessons
"What are the most important risk management lessons?"
"What mistakes should I avoid when trading options?"
"What are the key Phil Town Rule 1 principles?"

# Symbol-specific advice
"What lessons do we have about trading {symbol}?"
"What was our P/L history on {symbol}?"

# Risk warnings
"What critical failures have we had recently?"
"What trades resulted in losses and why?"
```

## Verification

The system now:
1. ✅ Queries Vertex AI RAG BEFORE each trading session
2. ✅ Displays critical warnings if found
3. ✅ Passes advice to trading execution
4. ✅ Syncs trades back to RAG after execution
5. ✅ Runs entirely in CI (bypasses sandbox SSL limitations)

## Impact

- **Before**: Same mistakes repeated because lessons weren't consulted
- **After**: True bidirectional learning - read lessons before trading, write lessons after

## Sources

- [Vertex AI RAG Engine Overview](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview)
- [Ground Responses Using RAG](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/ground-responses-using-rag)
- [ADK Vertex AI RAG Engine](https://github.com/arjunprabhulal/adk-vertex-ai-rag-engine)
- [Google Developers Blog - RAG Engine](https://developers.googleblog.com/en/vertex-ai-rag-engine-a-developers-tool/)
