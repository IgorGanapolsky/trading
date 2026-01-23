# LL-300: Dialogflow RAG Query Fix - Irrelevant Lessons Returned

**ID**: LL-300
**Date**: 2026-01-23
**Severity**: MEDIUM
**Category**: Integration Bug
**Status**: FIXED

## What Happened
Dialogflow returned irrelevant failure lessons (LL-272, LL-282, LL-223) when user asked "How much money did we make today and why?" on a day with no trades.

## Root Cause
1. On no-trade days, `query_rag_hybrid()` used user's raw query
2. Query "How much money did we make today" matched keywords in failure lessons
3. RAG semantic search found "money", "make", "today" in failure case studies
4. Returned random failure lessons instead of relevant trading context

## The Fix
In `src/agents/dialogflow_webhook.py`:
```python
# When no trades, use relevant query instead of user query
if trades_today == 0:
    rag_query = "trading signals market conditions iron condor entry criteria"
else:
    rag_query = user_query
results, source = query_rag_hybrid(rag_query, top_k=3)
```

## Key Insight
RAG semantic search matches tokens, not intent. When user asks about P/L:
- If trades exist → use their query to find relevant context
- If no trades → query for "why no trades" context (signals, market conditions)

## Prevention
1. Always consider context when routing RAG queries
2. No-trade days need different query strategy than trade days
3. Test Dialogflow with various edge cases (no trades, market closed, etc.)

## Related
- LL-226: Trade Data Source Priority Bug
- LL-273: CTO Failure - Stale Data Led to Misinformation

## Tags
dialogflow, rag, webhook, bug-fix, query-routing
